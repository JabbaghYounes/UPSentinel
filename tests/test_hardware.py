"""Tests for hardware reading with mocked I2C."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ups.hardware import I2CError, read_electrical_status


def _mock_read_word(addr: int, reg: int) -> int:
    """Simulate INA219 register reads (little-endian as smbus2 returns)."""
    # Bus voltage register (0x02): 7.4V -> raw = (7400/4) << 3 = 1850 << 3 = 14800
    # In big-endian: 0x39D0, smbus2 returns swapped: 0xD039
    if reg == 0x02:
        be_val = 14800  # (7.4V / 0.004) << 3
        return ((be_val >> 8) & 0xFF) | ((be_val & 0xFF) << 8)
    # Shunt voltage register (0x01): -10mV -> raw = -1000 (signed)
    # -1000 = 0xFC18, smbus2 returns swapped: 0x18FC
    if reg == 0x01:
        raw = -1000 & 0xFFFF  # unsigned representation
        return ((raw >> 8) & 0xFF) | ((raw & 0xFF) << 8)
    return 0


class TestReadElectricalStatus:
    """Tests for read_electrical_status with mocked SMBus."""

    @patch("ups.hardware.SMBus")
    def test_successful_read(self, mock_smbus_cls: MagicMock) -> None:
        mock_bus = MagicMock()
        mock_bus.read_word_data.side_effect = _mock_read_word
        mock_smbus_cls.return_value.__enter__ = MagicMock(return_value=mock_bus)
        mock_smbus_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = read_electrical_status(bus_num=1, addr=0x42)

        assert "voltage" in result
        assert "current" in result
        assert "power" in result
        assert result["voltage"] > 0
        assert isinstance(result["voltage"], float)

    @patch("ups.hardware.SMBus")
    def test_voltage_plausible(self, mock_smbus_cls: MagicMock) -> None:
        mock_bus = MagicMock()
        mock_bus.read_word_data.side_effect = _mock_read_word
        mock_smbus_cls.return_value.__enter__ = MagicMock(return_value=mock_bus)
        mock_smbus_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = read_electrical_status(bus_num=1, addr=0x42)

        # 7.4V expected from our mock
        assert 7.0 <= result["voltage"] <= 8.0

    @patch("ups.hardware.SMBus")
    def test_negative_current(self, mock_smbus_cls: MagicMock) -> None:
        mock_bus = MagicMock()
        mock_bus.read_word_data.side_effect = _mock_read_word
        mock_smbus_cls.return_value.__enter__ = MagicMock(return_value=mock_bus)
        mock_smbus_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = read_electrical_status(bus_num=1, addr=0x42)

        # Negative shunt voltage = negative current (discharging)
        assert result["current"] < 0

    @patch("ups.hardware.SMBus")
    def test_bus_not_found(self, mock_smbus_cls: MagicMock) -> None:
        mock_smbus_cls.side_effect = FileNotFoundError("/dev/i2c-1")

        with pytest.raises(I2CError, match="not found"):
            read_electrical_status(bus_num=1, addr=0x42)

    @patch("ups.hardware.SMBus")
    def test_device_not_responding(self, mock_smbus_cls: MagicMock) -> None:
        mock_bus = MagicMock()
        mock_bus.read_word_data.side_effect = OSError("Remote I/O error")
        mock_smbus_cls.return_value.__enter__ = MagicMock(return_value=mock_bus)
        mock_smbus_cls.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises(I2CError, match="Failed to communicate"):
            read_electrical_status(bus_num=1, addr=0x42)

    @patch("ups.hardware.SMBus")
    def test_custom_bus_and_addr(self, mock_smbus_cls: MagicMock) -> None:
        mock_bus = MagicMock()
        mock_bus.read_word_data.side_effect = _mock_read_word
        mock_smbus_cls.return_value.__enter__ = MagicMock(return_value=mock_bus)
        mock_smbus_cls.return_value.__exit__ = MagicMock(return_value=False)

        read_electrical_status(bus_num=3, addr=0x45)

        mock_smbus_cls.assert_called_once_with(3)
