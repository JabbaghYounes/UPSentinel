"""Configuration loading for UPS HAT (B) indicator.

Priority (highest to lowest):
    1. CLI flags
    2. Environment variables (UPS_I2C_BUS, UPS_I2C_ADDR)
    3. Config file (~/.config/ups-hat-b/config.toml)
    4. Built-in defaults
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]
from pathlib import Path

_DEFAULT_CONFIG_PATH = Path.home() / ".config" / "ups-hat-b" / "config.toml"

# Default voltage curve: (voltage, percent) pairs for 2S Li-ion
_DEFAULT_CURVE: list[tuple[float, int]] = [
    (6.0, 0),
    (6.4, 5),
    (6.8, 10),
    (7.0, 20),
    (7.2, 40),
    (7.4, 60),
    (7.6, 80),
    (7.9, 90),
    (8.2, 95),
    (8.4, 100),
]


@dataclass
class Config:
    """Application configuration."""

    # I2C settings
    i2c_bus: int = 1
    i2c_addr: int = 0x42

    # Indicator settings
    interval: int = 5

    # Battery thresholds
    warn_percent: int = 20
    critical_percent: int = 10

    # Voltage curve
    voltage_curve: list[tuple[float, int]] = field(default_factory=lambda: list(_DEFAULT_CURVE))

    # Shutdown (opt-in, disabled by default)
    shutdown_enabled: bool = False
    shutdown_percent: int = 5


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration from TOML file.

    Args:
        config_path: Path to config file, or None for default location.

    Returns:
        Config with values from file merged over defaults.
    """
    cfg = Config()
    path = config_path or _DEFAULT_CONFIG_PATH

    if path.is_file():
        with open(path, "rb") as f:
            data = tomllib.load(f)
        _apply_toml(cfg, data)

    _apply_env(cfg)
    return cfg


def _apply_toml(cfg: Config, data: dict) -> None:
    """Apply parsed TOML data to config."""
    i2c = data.get("i2c", {})
    if "bus" in i2c:
        cfg.i2c_bus = int(i2c["bus"])
    if "addr" in i2c:
        cfg.i2c_addr = int(str(i2c["addr"]), 0)

    indicator = data.get("indicator", {})
    if "interval" in indicator:
        cfg.interval = int(indicator["interval"])

    battery = data.get("battery", {})
    if "warn_percent" in battery:
        cfg.warn_percent = int(battery["warn_percent"])
    if "critical_percent" in battery:
        cfg.critical_percent = int(battery["critical_percent"])
    if "curve" in battery:
        curve_data = battery["curve"]
        cfg.voltage_curve = [(float(pair[0]), int(pair[1])) for pair in curve_data]

    shutdown = data.get("shutdown", {})
    if "enabled" in shutdown:
        cfg.shutdown_enabled = bool(shutdown["enabled"])
    if "percent" in shutdown:
        cfg.shutdown_percent = int(shutdown["percent"])


def _apply_env(cfg: Config) -> None:
    """Apply environment variable overrides."""
    bus_env = os.environ.get("UPS_I2C_BUS")
    if bus_env is not None:
        cfg.i2c_bus = int(bus_env)

    addr_env = os.environ.get("UPS_I2C_ADDR")
    if addr_env is not None:
        cfg.i2c_addr = int(addr_env, 0)
