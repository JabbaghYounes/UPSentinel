# UPS HAT (B) Desktop Indicator

Desktop tray indicator for the Waveshare UPS HAT (B) on Debian GNU/Linux 12 (Bookworm) aarch64.

## Features

- System tray icon showing battery state (full/good/low/critical)
- Menu with voltage, current, power, and percentage
- Charging/discharging icon variants
- Mock mode for testing without hardware (`--mock`)
- Configurable poll interval (`--interval`)

## Project Structure

```
ups-hat-b-indicator/
├── indicator.py          # Entry point (tray UI)
├── ups/
│   ├── hardware.py       # INA219 wrapper
│   ├── battery.py        # Voltage → percentage
│   └── model.py          # Shared dataclasses
├── icons/                # Battery state icons
├── systemd/              # User service unit
└── scripts/              # Helper scripts
```

## Requirements

- Python 3.11+
- Debian Bookworm (aarch64)
- Waveshare UPS HAT (B) connected via I2C

### System packages

```bash
sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1 python3-smbus2 i2c-tools
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

## Usage

```bash
# Run with real hardware
python3 indicator.py

# Run with mock data (for testing without UPS HAT)
python3 indicator.py --mock

# Custom poll interval (seconds)
python3 indicator.py --interval 10
```

## Autostart (systemd user service)

One-command install:

```bash
./scripts/install-user-service.sh
```

This copies the service file to `~/.config/systemd/user/`, enables it, and starts it immediately. The indicator will auto-start on login and restart on failure.

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
- Check the indicator is running: `systemctl --user status ups-hat-b-indicator`

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
