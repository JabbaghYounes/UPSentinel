"""Tests for bundled icon resolution.

Verifies every icon path returned by ``get_icon_name`` exists on disk so
typos and missing variants are caught at CI time, before deployment.
"""

from __future__ import annotations

import os

import pytest

from ups.backends import (
    ICON_CAUTION,
    ICON_DEFAULT,
    ICON_LOW,
    ICON_MAP,
    ICON_MISSING,
    ICONS_DIR,
    get_icon_name,
)
from ups.model import BatteryState, UPSStatus

EXPECTED_ICON_FILES = [
    "battery-caution.svg",
    "battery-caution-charging.svg",
    "battery-low.svg",
    "battery-low-charging.svg",
    "battery-good.svg",
    "battery-good-charging.svg",
    "battery-full.svg",
    "battery-full-charging.svg",
    "battery-missing.svg",
]


class TestIconsDirectory:
    def test_icons_dir_exists(self) -> None:
        assert ICONS_DIR.is_dir(), f"icons/ directory missing at {ICONS_DIR}"

    @pytest.mark.parametrize("filename", EXPECTED_ICON_FILES)
    def test_expected_icon_present(self, filename: str) -> None:
        assert (ICONS_DIR / filename).is_file(), f"missing bundled icon: {filename}"


class TestIconConstants:
    @pytest.mark.parametrize(
        "icon_path",
        [ICON_MISSING, ICON_DEFAULT, ICON_CAUTION, ICON_LOW],
    )
    def test_constant_resolves_to_existing_file(self, icon_path: str) -> None:
        assert os.path.isfile(icon_path)

    def test_icon_map_paths_exist(self) -> None:
        for _, _, discharge_icon, charge_icon in ICON_MAP:
            assert os.path.isfile(discharge_icon), discharge_icon
            assert os.path.isfile(charge_icon), charge_icon


class TestGetIconName:
    def test_status_none_returns_missing(self) -> None:
        assert get_icon_name(None) == ICON_MISSING

    def test_percent_none_returns_missing(self) -> None:
        status = UPSStatus(
            voltage=7.4, current=-0.1, power=0.74,
            percent=None, state=BatteryState.DISCHARGING,
        )
        assert get_icon_name(status) == ICON_MISSING

    @pytest.mark.parametrize("percent", [0, 5, 10, 11, 20, 21, 50, 51, 80, 81, 100])
    @pytest.mark.parametrize(
        "state",
        [BatteryState.CHARGING, BatteryState.DISCHARGING, BatteryState.UNKNOWN],
    )
    def test_returns_existing_path_across_buckets(
        self, percent: int, state: BatteryState
    ) -> None:
        status = UPSStatus(
            voltage=7.4, current=0.0, power=0.0,
            percent=percent, state=state,
        )
        path = get_icon_name(status)
        assert os.path.isfile(path), f"non-existent icon for {percent}% {state}: {path}"

    def test_charging_returns_charging_variant_at_full(self) -> None:
        status = UPSStatus(
            voltage=8.4, current=0.5, power=4.2,
            percent=95, state=BatteryState.CHARGING,
        )
        assert "charging" in get_icon_name(status)

    def test_discharging_does_not_return_charging_variant(self) -> None:
        status = UPSStatus(
            voltage=7.4, current=-0.5, power=3.7,
            percent=70, state=BatteryState.DISCHARGING,
        )
        assert "charging" not in get_icon_name(status)
