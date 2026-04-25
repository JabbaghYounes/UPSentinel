# UPS HAT (B) Desktop Indicator

Desktop tray indicator for the Waveshare UPS HAT (B) on Debian GNU/Linux 12 (Bookworm) aarch64.

## Features

- System tray icon showing battery state (full/good/low/critical)
- Menu with voltage, current, power, and percentage
- Charging/discharging icon variants
- **Multiple display backends** with auto-detection:
  - AppIndicator (GNOME, KDE, Xfce, MATE)
  - GTK Layer Shell widget (Raspberry Pi OS Bookworm Wayland)
  - Notification-only fallback
- **Bundled SVG icons** in `icons/` — white outline, blue fill matching
  Pi OS panel glyphs, red on critical state. The indicator no longer
  depends on the freedesktop icon theme, so two Pis with different theme
  configurations render identically.
- Mock mode for testing without hardware (`--mock`)
- Configurable poll interval (`--interval`)

## Project Structure

```
ups-hat-b-indicator/
├── indicator.py          # Entry point
├── ups/
│   ├── hardware.py       # INA219 I2C wrapper
│   ├── battery.py        # Voltage → percentage
│   ├── model.py          # Shared dataclasses
│   ├── config.py         # Configuration loading
│   └── backends/         # Display backends
│       ├── __init__.py   # Backend detection
│       ├── appindicator.py  # System tray (GNOME/KDE/Xfce)
│       ├── layershell.py    # Wayland widget (Pi OS)
│       └── notification.py  # Fallback (notifications only)
├── icons/                # Battery state icons
├── systemd/              # User service unit
└── scripts/              # Helper scripts
```

## Quick install

For Raspberry Pi OS Bookworm (and most desktop Linux), one command:

```bash
./install.sh
```

This installs system packages (with a follow-up `dpkg` verify because GIR
packages have been observed to silently fail to register on Pi OS), runs an
I2C smoke check, installs the Python package, writes a `config.toml` that
locks the backend to `appindicator` so two Pis side-by-side render
identically, and registers an autostart entry. On Pi OS / wlroots
compositors it uses an XDG `.desktop` file in `~/.config/autostart/`; on
other desktops it falls back to a `systemd --user` service. Override with
`--mode xdg|systemd` if you know which one you want.

After install, log into the desktop session (or reboot if auto-login is
enabled — `sudo raspi-config nonint get_autologin` returns `0` when on)
and the indicator appears in the panel tray.

The remainder of this README documents the same steps manually for users
who want finer control or are running on an unusual setup.

## Requirements

- Python 3.11+
- Debian Bookworm (aarch64)
- Waveshare UPS HAT (B) connected via I2C

### System packages

```bash
sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1 \
    libgtk-layer-shell0 gir1.2-gtklayershell-0.1 \
    python3-smbus2 i2c-tools libnotify-bin

# Verify the GIR packages actually registered (silent failures observed
# on Pi OS Bookworm — re-run the install if either is missing):
dpkg -l gir1.2-ayatanaappindicator3-0.1 gir1.2-gtklayershell-0.1 | grep ^ii
```

### Desktop-specific tray support

**GNOME (Wayland/X11):**

```bash
sudo apt install gnome-shell-extension-appindicator
```

Then enable the extension via GNOME Extensions app or:

```bash
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

**KDE Plasma:** AppIndicator support is built-in; no extra packages needed.

**Raspberry Pi OS Bookworm (Wayland - default):**

The default Pi OS Bookworm desktop uses Wayland with wf-panel-pi, which does not
support AppIndicator. The indicator will automatically use GTK Layer Shell to
display a small floating widget in the top-right corner instead.

```bash
sudo apt install libgtk-layer-shell0 gir1.2-gtklayershell-0.1
```

The widget shows battery percentage with an icon and opens a detail menu on click.

**Raspberry Pi OS Bookworm (X11 - optional):**

If you switch to X11 mode via `raspi-config > Advanced Options > Wayland > X11`,
the standard AppIndicator tray icon will work without additional packages.

## Usage

```bash
# Run with real hardware (auto-detects best backend)
python3 indicator.py

# Run with mock data (for testing without UPS HAT)
python3 indicator.py --mock

# Custom poll interval (seconds)
python3 indicator.py --interval 10

# Force a specific display backend
python3 indicator.py --backend appindicator   # System tray icon
python3 indicator.py --backend layershell     # Floating widget (Wayland)
python3 indicator.py --backend notification   # Notifications only
```

## Autostart

Prefer `./install.sh` (described above) — it picks the right autostart
mechanism for your system. Two backends are supported:

- **XDG autostart** (`~/.config/autostart/ups-hat-b-indicator.desktop`) —
  used by default on Pi OS Bookworm and other wlroots compositors. The
  desktop session manager launches the entry directly, so the indicator
  inherits a working Wayland/DBus environment. Required on Pi OS under
  `wayvnc`, where `graphical-session.target` does not fire reliably and
  `systemctl --user` services therefore never trigger.
- **systemd `--user` service** — preferred on most desktop Linux where
  `graphical-session.target` is reached on login. Install standalone
  with `./scripts/install-user-service.sh` (or `./install.sh --mode systemd`).

`./scripts/install-user-service.sh` copies the service file to
`~/.config/systemd/user/`, enables it, and starts it. The indicator
auto-starts on graphical login and restarts on failure.

Manual install:

```bash
# Copy service file (substituting your project path)
mkdir -p ~/.config/systemd/user
sed "s|__INSTALL_DIR__|$(pwd)|g" systemd/ups-hat-b-indicator.service \
    > ~/.config/systemd/user/ups-hat-b-indicator.service

# Enable and start
systemctl --user daemon-reload
systemctl --user enable --now ups-hat-b-indicator
```

Management commands:

```bash
systemctl --user status ups-hat-b-indicator    # Check status
journalctl --user -u ups-hat-b-indicator -f    # Follow logs
systemctl --user restart ups-hat-b-indicator   # Restart
systemctl --user disable --now ups-hat-b-indicator  # Disable
```

## Configuration

Configuration file: `~/.config/ups-hat-b/config.toml`

All fields are optional; defaults apply when omitted.

```toml
[i2c]
bus = 1
addr = "0x42"

[indicator]
interval = 5       # poll interval in seconds
backend = "auto"   # auto, appindicator, layershell, notification

[battery]
warn_percent = 20
critical_percent = 10

# Custom voltage-to-percent curve: [[voltage, percent], ...]
curve = [
    [6.0, 0],
    [6.4, 5],
    [6.8, 10],
    [7.0, 20],
    [7.2, 40],
    [7.4, 60],
    [7.6, 80],
    [7.9, 90],
    [8.2, 95],
    [8.4, 100],
]

[shutdown]
enabled = false     # opt-in: set true to enable auto-shutdown
percent = 5         # shutdown when battery drops to this level
```

**Priority** (highest to lowest): CLI flags > environment variables > config file > defaults.

### Safe shutdown (opt-in)

Shutdown is **disabled by default**. When enabled, the indicator will call
`systemctl poweroff` exactly once when battery drops to `shutdown_percent`.

To enable:

1. Add to `config.toml`:
   ```toml
   [shutdown]
   enabled = true
   percent = 5
   ```

2. Ensure the user has permission to shutdown. Either:

   **Option A** - Polkit (default on most desktops, works without config):
   Most desktop sessions already allow the logged-in user to poweroff via polkit.

   **Option B** - Sudoers (for headless/service setups):
   ```bash
   echo "youruser ALL=(ALL) NOPASSWD: /usr/bin/systemctl poweroff" | \
       sudo tee /etc/sudoers.d/ups-shutdown
   ```

3. Verify with dry-run:
   ```bash
   python3 indicator.py --test-shutdown --config ~/.config/ups-hat-b/config.toml
   ```

## Environment Variables

- `UPS_I2C_BUS` - I2C bus number (default: `1`)
- `UPS_I2C_ADDR` - INA219 address (default: `0x42`)

## Development

Install dev tools:

```bash
pip install -e ".[dev]"
```

Lint:

```bash
ruff check .
```

Run tests (no hardware required):

```bash
pytest
```

I2C diagnostics:

```bash
./scripts/i2c-detect.sh
```

## Troubleshooting

**Icon not visible in system tray:**

- GNOME: Ensure `gnome-shell-extension-appindicator` is installed and enabled.
  Log out and back in after enabling.
- Xfce: Add "Indicator Plugin" to a panel.
- Raspberry Pi OS (Wayland): Install `gir1.2-gtklayershell-0.1` for the floating
  widget. The default wf-panel-pi does not support AppIndicator tray icons.
- Check the indicator is running: `systemctl --user status ups-hat-b-indicator`
- Check which backend is being used: `python3 indicator.py --log-level INFO --mock`

**"UPS: unavailable" in menu:**

- Run `./scripts/i2c-detect.sh` to verify the UPS HAT is detected at 0x42.
- Check I2C is enabled: `ls /dev/i2c-*` should list at least `/dev/i2c-1`.
- Verify permissions: your user should be in the `i2c` group (`sudo usermod -aG i2c $USER`, then log out/in).

**Wrong voltage/percentage readings:**

- The default curve assumes a 2S Li-ion pack (6.0V-8.4V). If your pack differs,
  customize the `[battery.curve]` in config.toml.
- Use `--log-level DEBUG` to see raw readings each poll cycle.

**Notifications not appearing:**

- Ensure a notification daemon is running (e.g., `dunst`, `mako`, or the desktop's built-in one).
- Test manually: `notify-send "Test" "Hello"`

**Service won't start:**

- Check logs: `journalctl --user -u ups-hat-b-indicator -n 50`
- Verify the service file path is correct: `systemctl --user cat ups-hat-b-indicator`
- Ensure `graphical-session.target` is reached: `systemctl --user is-active graphical-session.target`

**Pi OS Bookworm + wayvnc — service installs but never runs:**

Under `wayvnc` on Pi OS, the wayfire/labwc session does not signal
`graphical-session.target` to the user systemd manager, so a unit with
`WantedBy=graphical-session.target` is enabled but never triggered. Use
the XDG autostart path instead:

```bash
./install.sh --mode xdg
```

The desktop session reads `~/.config/autostart/*.desktop` directly when
the GUI starts, so the indicator launches with a working Wayland/DBus
environment regardless of whether `graphical-session.target` fires.

**Shutdown not working when enabled:**

- Run `python3 indicator.py --test-shutdown` to diagnose.
- Most desktop sessions allow poweroff via polkit. If running headless, configure sudoers.

## Logging

Logs are written to stderr, captured by journald when running as a service.

```bash
# View logs
journalctl --user -u ups-hat-b-indicator -f

# Run with debug logging
python3 indicator.py --log-level DEBUG --mock
```

Available levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.

## License

MIT - see [LICENSE](LICENSE) for details.
