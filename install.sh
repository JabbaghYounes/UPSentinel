#!/usr/bin/env bash
# UPSentinel — one-command installer.
#
# Designed for Raspberry Pi OS Bookworm + Waveshare UPS HAT (B), but also
# works on most desktop Linux. Detects the desktop session model and chooses
# XDG autostart (Pi OS / wlroots) or systemd --user (most other distros).
#
# Usage:
#   ./install.sh                   auto-detect autostart mechanism
#   ./install.sh --mode xdg        force XDG autostart
#   ./install.sh --mode systemd    force systemd --user service
#   ./install.sh --skip-apt        skip the apt step (deps already installed)
#   ./install.sh --force-config    overwrite ~/.config/ups-hat-b/config.toml
#   ./install.sh -h | --help       show this help

set -euo pipefail

# ---------- argument parsing ----------
MODE="auto"
SKIP_APT=0
FORCE_CONFIG=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)
            MODE="${2:-}"
            shift 2
            ;;
        --skip-apt)
            SKIP_APT=1
            shift
            ;;
        --force-config)
            FORCE_CONFIG=1
            shift
            ;;
        -h|--help)
            sed -n '2,14p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

if [[ "$MODE" != "auto" && "$MODE" != "xdg" && "$MODE" != "systemd" ]]; then
    echo "ERROR: --mode must be auto|xdg|systemd (got: $MODE)" >&2
    exit 2
fi

# ---------- helpers ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

red()    { printf "\033[31m%s\033[0m\n" "$*"; }
green()  { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
header() { printf "\n\033[1m== %s ==\033[0m\n" "$*"; }

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || {
        red "ERROR: required command not found: $1"
        exit 1
    }
}

# ---------- step 1: apt deps ----------
APT_PACKAGES=(
    python3-gi
    gir1.2-ayatanaappindicator3-0.1
    libgtk-layer-shell0
    gir1.2-gtklayershell-0.1
    python3-smbus2
    i2c-tools
    libnotify-bin
)

# Packages whose absence causes the AppIndicator/LayerShell auto-detection
# to silently fall through. We verify these explicitly after apt because on
# Pi OS Bookworm we've seen them not register from the first install.
VERIFY_PACKAGES=(
    gir1.2-ayatanaappindicator3-0.1
    gir1.2-gtklayershell-0.1
)

if [[ $SKIP_APT -eq 0 ]]; then
    header "Installing system dependencies"
    require_cmd sudo
    require_cmd apt
    sudo apt update
    sudo apt install -y "${APT_PACKAGES[@]}"

    header "Verifying GIR packages registered"
    missing=()
    for pkg in "${VERIFY_PACKAGES[@]}"; do
        if ! dpkg -l "$pkg" 2>/dev/null | grep -q "^ii"; then
            missing+=("$pkg")
        fi
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        yellow "Retrying missing packages: ${missing[*]}"
        sudo apt install -y "${missing[@]}"
        for pkg in "${missing[@]}"; do
            if ! dpkg -l "$pkg" 2>/dev/null | grep -q "^ii"; then
                red "ERROR: $pkg failed to install after retry."
                red "Check apt sources / mirror, then re-run."
                exit 1
            fi
        done
    fi
    green "All required GIR packages installed."
else
    yellow "Skipping apt (--skip-apt)."
fi

# ---------- step 2: enable I2C + put user in i2c group ----------
NEEDS_REBOOT=0

header "Enabling I2C interface"
if command -v raspi-config >/dev/null 2>&1; then
    # raspi-config nonint get_i2c: 0 = enabled, 1 = disabled
    if [[ "$(sudo raspi-config nonint get_i2c 2>/dev/null)" == "1" ]]; then
        sudo raspi-config nonint do_i2c 0
        green "I2C interface enabled (reboot required to take effect)."
        NEEDS_REBOOT=1
    else
        green "I2C already enabled."
    fi
else
    yellow "raspi-config not available — assuming I2C is already enabled."
fi

header "Ensuring user is in i2c group"
if id -nG "$USER" | tr ' ' '\n' | grep -qx 'i2c'; then
    green "$USER is already in the i2c group."
else
    if getent group i2c >/dev/null 2>&1; then
        sudo usermod -aG i2c "$USER"
        yellow "Added $USER to i2c group (re-login or reboot for membership to apply)."
        NEEDS_REBOOT=1
    else
        yellow "i2c group does not exist on this system — skipping."
    fi
fi

header "Checking UPS HAT on I2C bus 1"
if command -v i2cdetect >/dev/null 2>&1; then
    # sudo so the check works even before group membership applies in this shell
    if sudo i2cdetect -y 1 2>/dev/null | awk 'NR>1 {for(i=2;i<=NF;i++) if($i=="42") exit 0;} END {exit 1}'; then
        green "UPS HAT detected at 0x42."
    elif sudo i2cdetect -y 1 >/dev/null 2>&1; then
        yellow "I2C bus 1 readable but 0x42 not present — confirm the HAT is seated."
    else
        yellow "Could not read I2C bus 1 — likely needs reboot after enabling I2C."
    fi
else
    yellow "i2cdetect not available; skipping HAT presence check."
fi

# ---------- step 3: pip install ----------
header "Installing UPSentinel (pip editable)"
require_cmd python3
pip_cmd=(python3 -m pip install --user -e "$PROJECT_DIR")
if ! "${pip_cmd[@]}"; then
    yellow "pip install failed — retrying with --break-system-packages (PEP 668)"
    python3 -m pip install --user --break-system-packages -e "$PROJECT_DIR"
fi
green "Package installed."

# ---------- step 4: config.toml ----------
CONFIG_DIR="$HOME/.config/ups-hat-b"
CONFIG_FILE="$CONFIG_DIR/config.toml"

header "Configuring backend"
mkdir -p "$CONFIG_DIR"
if [[ -f "$CONFIG_FILE" && $FORCE_CONFIG -eq 0 ]]; then
    yellow "Existing config kept: $CONFIG_FILE (use --force-config to overwrite)"
else
    cat > "$CONFIG_FILE" <<'EOF'
# UPSentinel configuration — edit to taste.
# Available options documented in the project README.

[indicator]
# Lock the backend so both Pis (and any new deployment) render identically.
# Auto-detection chooses AppIndicator first, but we pin it here to avoid
# a missing GIR silently falling back to LayerShell or notification-only.
backend = "appindicator"
EOF
    green "Wrote $CONFIG_FILE"
fi

# ---------- step 5: bundled icons into hicolor ----------
# AppIndicatorBackend self-installs these on first launch, but seeding them
# now means the panel sees our SVGs on its very first scan after install.
header "Installing bundled icons into hicolor"
if python3 -c "from ups.icon_install import ensure_user_icons_installed; from pathlib import Path; n = ensure_user_icons_installed(Path('${PROJECT_DIR}/icons')); print(f'  installed/updated {n} icon(s)')"; then
    green "Icons synced to ~/.local/share/icons/hicolor/scalable/status/"
else
    yellow "Icon pre-install skipped (will self-install on first indicator launch)."
fi

# ---------- step 6: autostart mechanism ----------
detect_mode() {
    # Pi OS / wlroots heuristic: wayfire/labwc binary present, OR /etc/os-release
    # identifies Raspberry Pi OS / Raspbian. Under wayvnc on these compositors,
    # graphical-session.target does NOT fire reliably, so XDG autostart is the
    # path that actually works.
    if command -v wayfire >/dev/null 2>&1 || command -v labwc >/dev/null 2>&1; then
        echo "xdg"
        return
    fi
    if [[ -r /etc/os-release ]] && grep -qiE 'raspbian|raspberry pi os' /etc/os-release; then
        echo "xdg"
        return
    fi
    echo "systemd"
}

if [[ "$MODE" == "auto" ]]; then
    MODE=$(detect_mode)
    yellow "Auto-detected autostart mode: $MODE"
fi

header "Installing autostart entry ($MODE)"
case "$MODE" in
    xdg)
        AUTOSTART_DIR="$HOME/.config/autostart"
        DESKTOP_FILE="$AUTOSTART_DIR/ups-hat-b-indicator.desktop"
        mkdir -p "$AUTOSTART_DIR"
        cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=UPS HAT (B) Indicator
Comment=Tray indicator for Waveshare UPS HAT (B)
Exec=/usr/bin/python3 ${PROJECT_DIR}/indicator.py
X-GNOME-Autostart-enabled=true
NoDisplay=false
EOF
        green "Wrote $DESKTOP_FILE"

        # If a previous systemd install is hanging around, disable it so we
        # don't double-start the indicator.
        if systemctl --user is-enabled ups-hat-b-indicator 2>/dev/null | grep -q enabled; then
            yellow "Disabling stale systemd --user service so XDG autostart owns it."
            systemctl --user disable --now ups-hat-b-indicator || true
        fi
        ;;
    systemd)
        bash "$PROJECT_DIR/scripts/install-user-service.sh"
        ;;
esac

# ---------- step 7: auto-login note ----------
if command -v raspi-config >/dev/null 2>&1; then
    set +e
    autologin_state="$(sudo raspi-config nonint get_autologin 2>/dev/null)"
    set -e
    if [[ "$autologin_state" == "1" ]]; then
        yellow "Note: desktop auto-login is OFF. UPSentinel only starts after"
        yellow "you log into the desktop session (VNC or local). Enable with:"
        yellow "    sudo raspi-config  -> System Options -> Boot / Auto Login"
    fi
fi

# ---------- step 8: start in current session if possible ----------
STARTED_NOW=0
header "Starting indicator"
if [[ $NEEDS_REBOOT -eq 1 ]]; then
    yellow "Skipping immediate start — system needs reboot first"
    yellow "(I2C interface enabled and/or i2c group membership added)."
elif [[ "${XDG_SESSION_TYPE:-tty}" != "wayland" && "${XDG_SESSION_TYPE:-tty}" != "x11" ]]; then
    yellow "Not in a desktop session ($XDG_SESSION_TYPE) — indicator will start"
    yellow "automatically on next desktop login."
else
    # Kill any old instance before starting a fresh one
    pkill -f "${PROJECT_DIR}/indicator.py" 2>/dev/null || true
    nohup /usr/bin/python3 "${PROJECT_DIR}/indicator.py" \
        >/tmp/ups-hat-b-indicator.log 2>&1 &
    disown
    sleep 1
    if pgrep -f "${PROJECT_DIR}/indicator.py" >/dev/null; then
        green "Indicator started in this session (logs: /tmp/ups-hat-b-indicator.log)"
        STARTED_NOW=1
    else
        yellow "Tried to start in this session but no process is running —"
        yellow "check /tmp/ups-hat-b-indicator.log for errors."
    fi
fi

# ---------- summary ----------
header "Install complete"
cat <<EOF
Backend:       appindicator (locked in $CONFIG_FILE)
Autostart:     $MODE
Project:       $PROJECT_DIR
EOF

if [[ $NEEDS_REBOOT -eq 1 ]]; then
    yellow ""
    yellow "REBOOT REQUIRED before the indicator can read the UPS HAT:"
    yellow "    sudo reboot"
    yellow ""
    yellow "After reboot the indicator will appear in the panel tray automatically"
    yellow "(assuming desktop auto-login is on, which is the Pi OS default)."
elif [[ $STARTED_NOW -eq 1 ]]; then
    green ""
    green "The indicator is running now and will auto-start on next login."
    green "Verify:  pgrep -af indicator.py"
else
    cat <<EOF

Indicator will start automatically on next desktop login.
Verify after login:  pgrep -af indicator.py

To run manually right now (must be from a desktop session, not SSH):
    python3 $PROJECT_DIR/indicator.py --log-level INFO
EOF
fi

if [[ "$MODE" == "systemd" ]]; then
    cat <<EOF

Service logs (systemd mode):
    journalctl --user -u ups-hat-b-indicator -f
EOF
fi
