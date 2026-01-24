"""Battery percentage estimation from voltage readings.

Converts raw voltage from the UPS HAT (B) (2S Li-ion pack) to a
battery percentage using a piecewise-linear discharge curve, and
infers charging/discharging state from current sign.
"""

from __future__ import annotations

from ups.model import BatteryState, ElectricalStatus, UPSStatus

# Default thresholds (percent)
WARN_PERCENT = 20
CRITICAL_PERCENT = 10

# Default 2S Li-ion discharge curve: (voltage, percent) pairs
DEFAULT_VOLTAGE_CURVE: list[tuple[float, int]] = [
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

# Current threshold below which state is "unknown" (noise floor)
_CURRENT_THRESHOLD = 0.005  # 5 mA


def voltage_to_percent(
    voltage: float | None,
    curve: list[tuple[float, int]] | None = None,
) -> int | None:
    """Map battery voltage to percentage using the discharge curve.

    Args:
        voltage: Battery pack voltage in volts, or None if unavailable.
        curve: Optional custom voltage curve. Uses default if None.

    Returns:
        Integer percent (0-100), or None if voltage is invalid/missing.
    """
    if voltage is None or voltage <= 0:
        return None

    voltage_curve = curve or DEFAULT_VOLTAGE_CURVE

    # Clamp to curve bounds
    if voltage <= voltage_curve[0][0]:
        return 0
    if voltage >= voltage_curve[-1][0]:
        return 100

    # Linear interpolation between curve points
    for i in range(1, len(voltage_curve)):
        v_low, p_low = voltage_curve[i - 1]
        v_high, p_high = voltage_curve[i]
        if voltage <= v_high:
            ratio = (voltage - v_low) / (v_high - v_low)
            return int(p_low + ratio * (p_high - p_low))

    return 100


def infer_state(current: float | None) -> BatteryState:
    """Infer battery state from current reading.

    Args:
        current: Current in amps. Positive = charging, negative = discharging.

    Returns:
        BatteryState enum value.
    """
    if current is None:
        return BatteryState.UNKNOWN
    if current > _CURRENT_THRESHOLD:
        return BatteryState.CHARGING
    if current < -_CURRENT_THRESHOLD:
        return BatteryState.DISCHARGING
    return BatteryState.UNKNOWN


def evaluate(
    electrical: ElectricalStatus,
    curve: list[tuple[float, int]] | None = None,
) -> UPSStatus:
    """Build a full UPSStatus from raw electrical readings.

    Args:
        electrical: Raw voltage/current/power readings.
        curve: Optional custom voltage curve.

    Returns:
        UPSStatus with computed percent and state.
    """
    percent = voltage_to_percent(electrical.voltage, curve)
    state = infer_state(electrical.current)
    return UPSStatus(
        voltage=electrical.voltage,
        current=electrical.current,
        power=electrical.power,
        percent=percent,
        state=state,
    )
