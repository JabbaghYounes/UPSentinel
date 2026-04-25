# Development

## Project structure

```
UPSentinel/
├── indicator.py          # Entry point: CLI + config merge + signal handling
├── install.sh            # One-command installer
├── ups/
│   ├── hardware.py       # INA219 I2C wrapper (smbus2, big-endian swap)
│   ├── battery.py        # Voltage → percentage, current sign → state
│   ├── model.py          # Shared dataclasses
│   ├── config.py         # Configuration loading (TOML + env + defaults)
│   └── backends/         # Display backends
│       ├── __init__.py   # StatusBackend ABC, ICON_MAP, detect_backend
│       ├── appindicator.py  # System tray (GNOME/KDE/Xfce/MATE)
│       ├── layershell.py    # Wayland widget (Pi OS)
│       └── notification.py  # Fallback (notifications only)
├── icons/                # Bundled SVG icons (white outline + #0F71CB fill)
├── systemd/              # User service unit (template with __INSTALL_DIR__)
├── scripts/              # Helper scripts (i2c-detect, install-user-service)
├── tests/                # pytest suite — no hardware required
└── docs/                 # This documentation
```

## Dev install

```bash
pip install -e ".[dev]"
```

Adds pytest and ruff.

## Lint

```bash
ruff check .
```

## Tests

The test suite mocks `ups.hardware.SMBus` and patches backend
availability helpers, so no real hardware or display server is
required.

```bash
# Full suite
pytest

# Single file / class / case
pytest tests/test_battery.py
pytest tests/test_battery.py::TestVoltageToPercent
pytest tests/test_battery.py::TestVoltageToPercent::test_interpolation_midpoint
```

## I2C diagnostics

```bash
./scripts/i2c-detect.sh
```

Confirms the UPS HAT is reachable at `0x42` on bus 1.

## Architecture notes

`StatusBackend` (in `ups/backends/__init__.py`) owns the cross-cutting
logic — polling, threshold gating, notification hysteresis, error
counting, and the opt-in shutdown. Concrete backends only implement
`start`, `stop`, `update_display`, and `name`. **When changing
indicator behaviour (not UI), edit the base class.**

Other things that span files:

- **Backend auto-detection order**: AppIndicator (if Ayatana GIR
  importable) → LayerShell (if Wayland session and GtkLayerShell
  importable) → Notification fallback.
- **Hysteresis in `check_thresholds`**: warn/critical notifications
  fire once when `percent <= threshold` and only re-arm when `percent
  > threshold + 2`. Preserve the gap or `tests/test_thresholds.py`
  fails.
- **INA219 byte order**: smbus2's `read_word_data`/`write_word_data`
  are little-endian, the INA219 is big-endian. `_read_word` /
  `_write_word` in `ups/hardware.py` swap bytes — don't call
  `bus.read_word_data` directly.
- **Battery state from current sign**: positive current = charging,
  negative = discharging, `|current| < 5 mA` = unknown (noise floor).
- **Mock mode** (`--mock`) bypasses I2C entirely in
  `StatusBackend.read_status` by generating random readings; tests
  rely on this too.

## systemd service template

`systemd/ups-hat-b-indicator.service` contains a literal
`__INSTALL_DIR__` placeholder. `scripts/install-user-service.sh` (and
`install.sh --mode systemd`) substitutes the repo path at install time
and drops the result in `~/.config/systemd/user/`. **Edit the
template, not the installed copy.**
