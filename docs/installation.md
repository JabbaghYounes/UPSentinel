# Installation

The recommended path is `./install.sh` from the repo root — see the
[Quick install](../README.md#quick-install) section in the main README.
This document covers what the installer does step-by-step and the
manual equivalents for users who want finer control or are on an
unusual setup.

## What `install.sh` does

1. **`apt install`** the GTK / GIR / I2C system packages.
2. **`dpkg -l` verify** the GIR packages registered (silent failures
   observed on Pi OS Bookworm).
3. **`raspi-config nonint do_i2c 0`** if the I2C interface is
   disabled.
4. **`usermod -aG i2c $USER`** if you are not already a member.
5. **`pip install -e .`** with a `--break-system-packages` fallback
   for PEP 668 distributions.
6. **Writes `~/.config/ups-hat-b/config.toml`** locking the backend to
   `appindicator` so multiple Pis render identically.
7. **Registers an autostart entry** — XDG `.desktop` for Pi OS /
   wlroots compositors, `systemd --user` elsewhere. Override with
   `--mode xdg|systemd`.
8. **Starts the indicator immediately** if you ran the script from
   inside a desktop session (so the tray icon appears without you
   doing anything else).
9. Reports clearly whether a reboot is required (it is, the first
   time, if I2C was just enabled or you were just added to the i2c
   group).

## Requirements

- Python 3.11+
- Debian Bookworm (aarch64)
- Waveshare UPS HAT (B) connected via I2C

## Manual install

### System packages

```bash
sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1 \
    libgtk-layer-shell0 gir1.2-gtklayershell-0.1 \
    python3-smbus2 i2c-tools libnotify-bin

# Verify the GIR packages actually registered (silent failures observed
# on Pi OS Bookworm — re-run apt install if either is missing):
dpkg -l gir1.2-ayatanaappindicator3-0.1 gir1.2-gtklayershell-0.1 | grep ^ii
```

### Enable I2C (Raspberry Pi only)

```bash
sudo raspi-config nonint do_i2c 0
sudo usermod -aG i2c "$USER"
# Reboot for both to take effect:
sudo reboot
```

### Install the package

```bash
cd /path/to/UPSentinel
pip install -e .
# If pip refuses with PEP 668 (externally-managed-environment):
pip install --user --break-system-packages -e .
```

### Desktop-specific tray support

**GNOME (Wayland/X11):**

```bash
sudo apt install gnome-shell-extension-appindicator
gnome-extensions enable appindicatorsupport@rgcjonas.gmail.com
```

Log out and back in for the extension to take effect.

**Xfce:**

```bash
sudo apt install xfce4-indicator-plugin
```

Add the "Indicator Plugin" to a panel via Panel Preferences.

**MATE:**

```bash
sudo apt install mate-indicator-applet
```

Add "Indicator Applet" to a panel.

**KDE Plasma:** AppIndicator support is built-in; no extra packages
needed.

**Raspberry Pi OS Bookworm (Wayland — default):** the default Pi OS
Bookworm desktop uses Wayland with `wf-panel-pi`. AppIndicator works
once `gir1.2-ayatanaappindicator3-0.1` is installed (the apt block
above includes it). If AppIndicator is unavailable the indicator falls
back to a GTK Layer Shell floating widget.

**Raspberry Pi OS Bookworm (X11 — optional):** if you switch to X11 mode
via `raspi-config > Advanced Options > Wayland > X11`, the standard
AppIndicator tray works without additional packages.

## Next steps

- [Configure the indicator](configuration.md)
- [Set up autostart](autostart.md)
- [Enable safe shutdown](shutdown.md)
