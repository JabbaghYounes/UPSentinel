# Usage

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

# Dry-run the shutdown path without actually shutting down
python3 indicator.py --test-shutdown

# Verbose output for diagnosing
python3 indicator.py --log-level DEBUG --mock
```

Available log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.

## Mock mode

`--mock` bypasses I2C entirely and generates random readings in the
valid voltage range. Useful for verifying the icon, menu, and
notification paths without the HAT plugged in.

## Environment variables

- `UPS_I2C_BUS` — I2C bus number (default: `1`)
- `UPS_I2C_ADDR` — INA219 address (default: `0x42`)

## Configuration priority

Highest wins:

1. CLI flags
2. Environment variables
3. `~/.config/ups-hat-b/config.toml`
4. Built-in defaults

See [configuration.md](configuration.md) for the full schema.
