# Autostart

`./install.sh` picks the right autostart mechanism for your system —
prefer it over the manual paths below. Two backends are supported:

- **XDG autostart** (`~/.config/autostart/ups-hat-b-indicator.desktop`)
  — used by default on Pi OS Bookworm and other wlroots compositors.
  The desktop session manager launches the entry directly, so the
  indicator inherits a working Wayland/DBus environment. **Required on
  Pi OS under `wayvnc`**, where `graphical-session.target` does not
  fire reliably and `systemctl --user` services therefore never
  trigger. See [troubleshooting](troubleshooting.md) for the symptom.
- **systemd `--user` service** — preferred on most desktop Linux where
  `graphical-session.target` is reached on login.

## XDG autostart (Pi OS / wlroots)

Either run `./install.sh --mode xdg` or create the file manually:

```bash
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/ups-hat-b-indicator.desktop <<EOF
[Desktop Entry]
Type=Application
Name=UPS HAT (B) Indicator
Comment=Tray indicator for Waveshare UPS HAT (B)
Exec=/usr/bin/python3 $HOME/UPSentinel/indicator.py
X-GNOME-Autostart-enabled=true
NoDisplay=false
EOF
```

Adjust the `Exec=` path if the repo lives somewhere other than
`~/UPSentinel`.

The indicator launches when the desktop session starts (i.e. on the
next login or reboot, not the moment the file is dropped).

## systemd --user service

Either run `./install.sh --mode systemd` or
`./scripts/install-user-service.sh` standalone, both of which:

1. Substitute the repo path into
   `systemd/ups-hat-b-indicator.service`.
2. Drop the result in `~/.config/systemd/user/`.
3. `daemon-reload` and `enable --now`.

### Manual install

```bash
mkdir -p ~/.config/systemd/user
sed "s|__INSTALL_DIR__|$(pwd)|g" systemd/ups-hat-b-indicator.service \
    > ~/.config/systemd/user/ups-hat-b-indicator.service

systemctl --user daemon-reload
systemctl --user enable --now ups-hat-b-indicator
```

### Management commands

```bash
systemctl --user status ups-hat-b-indicator        # Check status
journalctl --user -u ups-hat-b-indicator -f        # Follow logs
systemctl --user restart ups-hat-b-indicator       # Restart
systemctl --user disable --now ups-hat-b-indicator # Disable
```

## Auto-login (Pi OS)

XDG autostart fires when the desktop session *starts*, not on system
boot directly. Auto-login is the Pi OS default (`raspi-config` →
"Boot to Desktop" → "B4 auto-login"); leave it on and the indicator
appears after every reboot without manual login. If auto-login is
disabled the indicator only starts when you log into the desktop.

Check current state:

```bash
sudo raspi-config nonint get_autologin
# 0 = enabled, 1 = disabled
```

SSH-only access does **not** trigger autostart — SSH is a TTY
session, not a graphical one.
