"""Shared dataclasses for UPS status."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BatteryState(Enum):
    CHARGING = "charging"
    DISCHARGING = "discharging"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ElectricalStatus:
    """Raw electrical readings from the INA219."""

    voltage: float  # Volts
    current: float  # Amps (positive = charging, negative = discharging)
    power: float  # Watts


@dataclass(frozen=True)
class UPSStatus:
    """Processed UPS status with battery percentage and state."""

    voltage: float  # Volts
    current: float  # Amps
    power: float  # Watts
    percent: int | None  # 0-100, or None if unknown
    state: BatteryState
