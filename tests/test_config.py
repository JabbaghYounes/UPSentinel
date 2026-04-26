"""Tests for configuration loading."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from ups.config import Config, load_config


class TestDefaults:
    """Tests for default configuration values."""

    def test_default_bus(self) -> None:
        cfg = Config()
        assert cfg.i2c_bus == 1

    def test_default_addr(self) -> None:
        cfg = Config()
        assert cfg.i2c_addr == 0x42

    def test_default_interval(self) -> None:
        cfg = Config()
        assert cfg.interval == 5

    def test_default_thresholds(self) -> None:
        cfg = Config()
        assert cfg.warn_percent == 20
        assert cfg.critical_percent == 10

    def test_default_shutdown_disabled(self) -> None:
        cfg = Config()
        assert cfg.shutdown_enabled is False
        assert cfg.shutdown_percent == 5

    def test_default_curve_has_entries(self) -> None:
        cfg = Config()
        assert len(cfg.voltage_curve) == 10
        assert cfg.voltage_curve[0] == (6.0, 0)
        assert cfg.voltage_curve[-1] == (8.4, 100)

    def test_default_layershell_placement(self) -> None:
        cfg = Config()
        assert cfg.layershell_anchor_top is True
        assert cfg.layershell_anchor_right is True
        assert cfg.layershell_anchor_bottom is False
        assert cfg.layershell_anchor_left is False
        assert cfg.layershell_margin_top == 2
        assert cfg.layershell_margin_right == 110
        assert cfg.layershell_margin_bottom == 0
        assert cfg.layershell_margin_left == 0


class TestLoadFromFile:
    """Tests for loading config from TOML files."""

    def _write_toml(self, content: str) -> Path:
        f = tempfile.NamedTemporaryFile(suffix=".toml", delete=False, mode="w")
        f.write(content)
        f.close()
        return Path(f.name)

    def test_nonexistent_file_uses_defaults(self) -> None:
        cfg = load_config(Path("/nonexistent/path.toml"))
        assert cfg.i2c_bus == 1
        assert cfg.interval == 5

    def test_full_config(self) -> None:
        path = self._write_toml("""
[i2c]
bus = 3
addr = "0x45"

[indicator]
interval = 10

[battery]
warn_percent = 25
critical_percent = 15
curve = [[6.0, 0], [7.0, 50], [8.4, 100]]

[shutdown]
enabled = true
percent = 3
""")
        try:
            cfg = load_config(path)
            assert cfg.i2c_bus == 3
            assert cfg.i2c_addr == 0x45
            assert cfg.interval == 10
            assert cfg.warn_percent == 25
            assert cfg.critical_percent == 15
            assert cfg.voltage_curve == [(6.0, 0), (7.0, 50), (8.4, 100)]
            assert cfg.shutdown_enabled is True
            assert cfg.shutdown_percent == 3
        finally:
            os.unlink(path)

    def test_partial_config_keeps_defaults(self) -> None:
        path = self._write_toml("""
[indicator]
interval = 15
""")
        try:
            cfg = load_config(path)
            assert cfg.interval == 15
            assert cfg.i2c_bus == 1  # default
            assert cfg.i2c_addr == 0x42  # default
            assert cfg.warn_percent == 20  # default
            assert len(cfg.voltage_curve) == 10  # default
        finally:
            os.unlink(path)

    def test_layershell_overrides(self) -> None:
        path = self._write_toml("""
[layershell]
anchor_top = false
anchor_bottom = true
anchor_right = false
anchor_left = true
margin_top = 0
margin_bottom = 4
margin_left = 12
margin_right = 0
""")
        try:
            cfg = load_config(path)
            assert cfg.layershell_anchor_top is False
            assert cfg.layershell_anchor_bottom is True
            assert cfg.layershell_anchor_right is False
            assert cfg.layershell_anchor_left is True
            assert cfg.layershell_margin_top == 0
            assert cfg.layershell_margin_bottom == 4
            assert cfg.layershell_margin_left == 12
            assert cfg.layershell_margin_right == 0
        finally:
            os.unlink(path)

    def test_layershell_partial_keeps_defaults(self) -> None:
        path = self._write_toml("""
[layershell]
margin_right = 250
""")
        try:
            cfg = load_config(path)
            assert cfg.layershell_margin_right == 250
            assert cfg.layershell_margin_top == 2  # default
            assert cfg.layershell_anchor_top is True  # default
        finally:
            os.unlink(path)

    def test_decimal_addr(self) -> None:
        path = self._write_toml("""
[i2c]
addr = "66"
""")
        try:
            cfg = load_config(path)
            assert cfg.i2c_addr == 66
        finally:
            os.unlink(path)


class TestEnvOverride:
    """Tests for environment variable overrides."""

    def test_bus_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UPS_I2C_BUS", "7")
        cfg = load_config(Path("/nonexistent"))
        assert cfg.i2c_bus == 7

    def test_addr_env_hex(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UPS_I2C_ADDR", "0x50")
        cfg = load_config(Path("/nonexistent"))
        assert cfg.i2c_addr == 0x50

    def test_env_overrides_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        f = tempfile.NamedTemporaryFile(suffix=".toml", delete=False, mode="w")
        f.write("[i2c]\nbus = 3\n")
        f.close()
        path = Path(f.name)
        try:
            monkeypatch.setenv("UPS_I2C_BUS", "9")
            cfg = load_config(path)
            assert cfg.i2c_bus == 9  # env wins over file
        finally:
            os.unlink(path)
