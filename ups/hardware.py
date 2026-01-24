"""INA219 hardware abstraction for UPS HAT (B).

Reads voltage, current, and power from the INA219 current/power monitor
on the Waveshare UPS HAT (B) via I2C.
"""

from __future__ import annotations

from smbus2 import SMBus

# INA219 register addresses
_REG_CONFIG = 0x00
_REG_SHUNT_VOLTAGE = 0x01
_REG_BUS_VOLTAGE = 0x02
_REG_CALIBRATION = 0x05

# Configuration: 32V bus range, ±320mV shunt range, 12-bit ADC, continuous mode
_CONFIG_VALUE = 0x399F

# UPS HAT (B) shunt resistor value in ohms
_SHUNT_RESISTANCE = 0.1

# Calibration for internal current/power calculation
# current_lsb = 0.1mA, cal = 0.04096 / (current_lsb * R_shunt)
_CURRENT_LSB = 0.0001  # 0.1 mA per bit
_CAL_VALUE = 4096


class I2CError(Exception):
    """Raised when I2C communication fails."""


def _read_word(bus: SMBus, addr: int, reg: int) -> int:
    """Read a 16-bit big-endian word from a register."""
    data = bus.read_word_data(addr, reg)
    # smbus2 returns little-endian; INA219 sends big-endian
    return ((data & 0xFF) << 8) | ((data >> 8) & 0xFF)


def _write_word(bus: SMBus, addr: int, reg: int, value: int) -> None:
    """Write a 16-bit big-endian word to a register."""
    # Convert to little-endian for smbus2
    swapped = ((value & 0xFF) << 8) | ((value >> 8) & 0xFF)
    bus.write_word_data(addr, reg, swapped)


def _configure(bus: SMBus, addr: int) -> None:
    """Write configuration and calibration registers."""
    _write_word(bus, addr, _REG_CONFIG, _CONFIG_VALUE)
    _write_word(bus, addr, _REG_CALIBRATION, _CAL_VALUE)


def read_electrical_status(bus_num: int = 1, addr: int = 0x42) -> dict[str, float]:
    """Read voltage, current, and power from the UPS HAT (B).

    Args:
        bus_num: I2C bus number.
        addr: INA219 I2C address.

    Returns:
        Dictionary with keys 'voltage' (V), 'current' (A), 'power' (W).

    Raises:
        I2CError: If the I2C device cannot be read.
    """
    try:
        with SMBus(bus_num) as bus:
            _configure(bus, addr)

            # Bus voltage: register value >> 3, LSB = 4mV
            raw_bus = _read_word(bus, addr, _REG_BUS_VOLTAGE)
            voltage = (raw_bus >> 3) * 0.004

            # Shunt voltage: signed 16-bit, LSB = 10uV
            raw_shunt = _read_word(bus, addr, _REG_SHUNT_VOLTAGE)
            if raw_shunt & 0x8000:
                raw_shunt -= 0x10000
            shunt_voltage = raw_shunt * 0.00001

            # Current from shunt voltage and known resistance
            current = shunt_voltage / _SHUNT_RESISTANCE

            # Power
            power = voltage * abs(current)

            return {
                "voltage": round(voltage, 3),
                "current": round(current, 4),
                "power": round(power, 4),
            }
    except FileNotFoundError as e:
        raise I2CError(f"I2C bus {bus_num} not found: {e}") from e
    except OSError as e:
        raise I2CError(
            f"Failed to communicate with device 0x{addr:02X} on bus {bus_num}: {e}"
        ) from e
