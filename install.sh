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

# ---------- step 2: I2C smoke check ----------
header "Checking UPS HAT on I2C bus 1"
if command -v i2cdetect >/dev/null 2>&1; then
    if i2cdetect -y 1 2>/dev/null | grep -qE "(^4[0-9]:|\b42\b)"; then
        if i2cdetect -y 1 2>/dev/null | awk 'NR>1 {for(i=2;i<=NF;i++) if($i=="42") exit 0; } END {exit 1}'; then
            green "UPS HAT detected at 0x42."
        else
            yellow "I2C bus 1 readable but 0x42 not present — confirm the HAT is seated."
        fi
    else
        yellow "Could not read I2C bus 1 (need i2c group membership? sudo usermod -aG i2c \$USER)"
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

# ---------- step 5: autostart mechanism ----------
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

# ---------- step 6: auto-login note ----------
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

# ---------- summary ----------
header "Install complete"
cat <<EOF
Backend:       appindicator (locked in $CONFIG_FILE)
Autostart:     $MODE
Project:       $PROJECT_DIR

Verify after the next desktop login:
  pgrep -af indicator.py

Run manually right now (current session must be a desktop session):
  python3 $PROJECT_DIR/indicator.py --log-level INFO

Logs (systemd mode):
  journalctl --user -u ups-hat-b-indicator -f
EOF
