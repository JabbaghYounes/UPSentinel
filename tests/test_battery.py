"""Tests for battery percentage estimation and state inference."""

from __future__ import annotations

import pytest

from ups.battery import (
    evaluate,
    infer_state,
    voltage_to_percent,
)
from ups.model import BatteryState, ElectricalStatus


class TestVoltageToPercent:
    """Tests for voltage_to_percent mapping."""

    def test_none_returns_none(self) -> None:
        assert voltage_to_percent(None) is None

    def test_zero_returns_none(self) -> None:
        assert voltage_to_percent(0.0) is None

    def test_negative_returns_none(self) -> None:
        assert voltage_to_percent(-5.0) is None

    def test_below_curve_minimum(self) -> None:
        assert voltage_to_percent(5.0) == 0

    def test_at_curve_minimum(self) -> None:
        assert voltage_to_percent(6.0) == 0

    def test_above_curve_maximum(self) -> None:
        assert voltage_to_percent(9.0) == 100

    def test_at_curve_maximum(self) -> None:
        assert voltage_to_percent(8.4) == 100

    @pytest.mark.parametrize(
        "voltage,expected",
        [
            (6.4, 5),
            (7.0, 20),
            (7.2, 40),
            (7.4, 60),
            (7.6, 80),
            (7.9, 90),
            (8.2, 95),
        ],
    )
    def test_curve_points(self, voltage: float, expected: int) -> None:
        assert voltage_to_percent(voltage) == expected

    def test_interpolation_midpoint(self) -> None:
        # Between (7.0, 20) and (7.2, 40): midpoint 7.1 -> ~30
        result = voltage_to_percent(7.1)
        assert result is not None
        assert 28 <= result <= 31  # Allow int truncation

    def test_custom_curve(self) -> None:
        custom = [(3.0, 0), (4.2, 100)]
        assert voltage_to_percent(3.0, curve=custom) == 0
        assert voltage_to_percent(4.2, curve=custom) == 100
        result = voltage_to_percent(3.6, curve=custom)
        assert result is not None
        assert 45 <= result <= 55  # ~50%


class TestInferState:
    """Tests for charging/discharging state inference."""

    def test_none_current(self) -> None:
        assert infer_state(None) == BatteryState.UNKNOWN

    def test_zero_current(self) -> None:
        assert infer_state(0.0) == BatteryState.UNKNOWN

    def test_small_noise(self) -> None:
        assert infer_state(0.003) == BatteryState.UNKNOWN
        assert infer_state(-0.003) == BatteryState.UNKNOWN

    def test_positive_charging(self) -> None:
        assert infer_state(0.1) == BatteryState.CHARGING
        assert infer_state(1.5) == BatteryState.CHARGING

    def test_negative_discharging(self) -> None:
        assert infer_state(-0.1) == BatteryState.DISCHARGING
        assert infer_state(-2.0) == BatteryState.DISCHARGING

    def test_threshold_boundary(self) -> None:
        # Exactly at threshold (0.005) should be unknown
        assert infer_state(0.005) == BatteryState.UNKNOWN
        # Just above threshold
        assert infer_state(0.006) == BatteryState.CHARGING


class TestEvaluate:
    """Tests for the full evaluate pipeline."""

    def test_charging_full(self) -> None:
        es = ElectricalStatus(voltage=8.4, current=0.5, power=4.2)
        status = evaluate(es)
        assert status.percent == 100
        assert status.state == BatteryState.CHARGING

    def test_discharging_low(self) -> None:
        es = ElectricalStatus(voltage=6.8, current=-0.3, power=2.04)
        status = evaluate(es)
        assert status.percent == 10
        assert status.state == BatteryState.DISCHARGING

    def test_preserves_electrical_values(self) -> None:
        es = ElectricalStatus(voltage=7.4, current=-0.2, power=1.48)
        status = evaluate(es)
        assert status.voltage == 7.4
        assert status.current == -0.2
        assert status.power == 1.48

    def test_custom_curve(self) -> None:
        custom = [(3.0, 0), (4.2, 100)]
        es = ElectricalStatus(voltage=3.6, current=0.0, power=0.0)
        status = evaluate(es, curve=custom)
        assert status.percent is not None
        assert 45 <= status.percent <= 55
