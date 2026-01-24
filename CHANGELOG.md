# Changelog

## v1.0.0

- Tray indicator with battery state icons (full/good/low/critical)
- Charging/discharging icon variants
- Menu displaying voltage, current, power, percentage, and state
- Desktop notifications at configurable warn (20%) and critical (10%) thresholds
- Notification hysteresis to prevent repeated alerts
- Error-state UX: missing icon and notification after repeated I2C failures
- INA219 hardware abstraction with configurable I2C bus/address
- Voltage-to-percent mapping via configurable piecewise-linear curve
- TOML configuration file (~/.config/ups-hat-b/config.toml)
- CLI flags (--bus, --addr, --interval, --config, --mock, --log-level)
- Environment variable overrides (UPS_I2C_BUS, UPS_I2C_ADDR)
- Opt-in safe shutdown at configurable threshold (disabled by default)
- --test-shutdown dry-run for verifying permissions
- systemd user service with install helper script
- Structured logging to stderr/journal
- I2C diagnostics helper script
- Automated test suite (pytest, no hardware required)

## v0.4.0

- Added opt-in shutdown support (shutdown_enabled, shutdown_percent)
- Added --test-shutdown dry-run flag

## v0.3.0

- Added TOML config file support
- Added CLI flags (--bus, --addr, --interval, --config)
- Configuration priority: CLI > env > file > defaults

## v0.2.1

- Added systemd user service
- Added install helper script

## v0.2.0

- Added desktop notifications (warn/critical thresholds)
- Added notification hysteresis
- Added error-state UX (missing icon, error notifications)

## v0.1.0

- Initial tray indicator with battery icon
- Menu with status display
- Polling with configurable interval
- Mock mode for testing
- INA219 hardware reading
- Battery voltage-to-percent estimation
- Charging/discharging state inference
