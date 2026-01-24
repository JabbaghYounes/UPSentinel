"""UPS HAT (B) Desktop Indicator - Entry Point.

Displays a system tray icon showing UPS battery state, with a menu
providing voltage, current, power, and percentage information.
Sends desktop notifications at low/critical thresholds.
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import signal
import subprocess
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
gi.require_version("Notify", "0.7")

from gi.repository import AyatanaAppIndicator3 as AppIndicator3  # noqa: E402
from gi.repository import GLib, Gtk, Notify  # noqa: E402

from ups.battery import evaluate  # noqa: E402
from ups.config import Config, load_config  # noqa: E402
from ups.hardware import I2CError, read_electrical_status  # noqa: E402
from ups.model import BatteryState, ElectricalStatus, UPSStatus  # noqa: E402

log = logging.getLogger("ups-indicator")

# Number of consecutive read failures before notifying
_ERROR_NOTIFY_THRESHOLD = 3

# Icon name mapping: (min_percent, max_percent) -> icon_name
# Checked in order; first match wins.
_ICON_MAP: list[tuple[int, int, str, str]] = [
    # (min%, max%, discharging_icon, charging_icon)
    (0, 10, "battery-caution-symbolic", "battery-caution-charging-symbolic"),
    (11, 20, "battery-low-symbolic", "battery-low-charging-symbolic"),
    (21, 50, "battery-low-symbolic", "battery-good-charging-symbolic"),
    (51, 80, "battery-good-symbolic", "battery-good-charging-symbolic"),
    (81, 100, "battery-full-symbolic", "battery-full-charging-symbolic"),
]

_ICON_MISSING = "battery-missing-symbolic"
_ICON_DEFAULT = "battery-good-symbolic"

_APP_NAME = "UPS HAT (B)"


def _get_icon_name(status: UPSStatus | None) -> str:
    """Select an icon name based on UPS status."""
    if status is None or status.percent is None:
        return _ICON_MISSING

    charging = status.state == BatteryState.CHARGING

    for min_pct, max_pct, discharge_icon, charge_icon in _ICON_MAP:
        if min_pct <= status.percent <= max_pct:
            return charge_icon if charging else discharge_icon

    return _ICON_DEFAULT


def _format_status(status: UPSStatus | None) -> str:
    """Format status for display in menu."""
    if status is None:
        return "UPS: unavailable"

    pct = f"{status.percent}%" if status.percent is not None else "?%"
    return (
        f"{pct}  |  {status.voltage:.2f}V  "
        f"{status.current:.3f}A  {status.power:.2f}W  "
        f"[{status.state.value}]"
    )


class UPSIndicator:
    """System tray indicator for UPS HAT (B)."""

    def __init__(self, cfg: Config, mock: bool = False) -> None:
        self._cfg = cfg
        self._mock = mock
        self._status: UPSStatus | None = None

        # Notification state (hysteresis)
        self._notified_warn = False
        self._notified_critical = False

        # Shutdown state
        self._shutdown_triggered = False

        # Error tracking
        self._consecutive_failures = 0
        self._error_notified = False
        self._last_error: str = ""

        # Init notifications
        Notify.init(_APP_NAME)

        self._indicator = AppIndicator3.Indicator.new(
            "ups-hat-b-indicator",
            _ICON_DEFAULT,
            AppIndicator3.IndicatorCategory.HARDWARE,
        )
        self._indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

        log.info(
            "Starting indicator: bus=%d addr=0x%02X interval=%ds mock=%s",
            cfg.i2c_bus, cfg.i2c_addr, cfg.interval, mock,
        )

        self._build_menu()
        self._update()

    def _build_menu(self) -> None:
        """Build the indicator menu."""
        menu = Gtk.Menu()

        # Status line (non-interactive)
        self._status_item = Gtk.MenuItem(label="UPS: reading...")
        self._status_item.set_sensitive(False)
        menu.append(self._status_item)

        menu.append(Gtk.SeparatorMenuItem())

        # Quit
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self._on_quit)
        menu.append(quit_item)

        menu.show_all()
        self._indicator.set_menu(menu)

    def _read_status(self) -> UPSStatus | None:
        """Read UPS status from hardware or mock."""
        if self._mock:
            return self._mock_status()
        try:
            data = read_electrical_status(
                bus_num=self._cfg.i2c_bus,
                addr=self._cfg.i2c_addr,
            )
            electrical = ElectricalStatus(
                voltage=data["voltage"],
                current=data["current"],
                power=data["power"],
            )
            # Successful read: reset error state
            if self._consecutive_failures > 0:
                log.info("I2C read recovered after %d failures", self._consecutive_failures)
            self._consecutive_failures = 0
            self._error_notified = False
            self._last_error = ""
            status = evaluate(electrical, curve=self._cfg.voltage_curve)
            log.debug(
                "Read: %.2fV %.3fA %.2fW -> %s%% [%s]",
                status.voltage, status.current, status.power,
                status.percent, status.state.value,
            )
            return status
        except I2CError as e:
            self._last_error = str(e)
            self._consecutive_failures += 1
            log.warning("I2C read failed (%d): %s", self._consecutive_failures, e)
            self._handle_error()
            return None

    def _handle_error(self) -> None:
        """Handle read failures: notify after repeated errors."""
        if (
            self._consecutive_failures >= _ERROR_NOTIFY_THRESHOLD
            and not self._error_notified
        ):
            self._error_notified = True
            self._notify(
                "UPS Read Error",
                f"Cannot read UPS after {self._consecutive_failures} attempts.\n"
                f"{self._last_error}",
                "dialog-warning",
            )

    def _mock_status(self) -> UPSStatus:
        """Generate a mock UPS status for testing."""
        voltage = round(random.uniform(6.0, 8.4), 2)
        current = round(random.uniform(-1.0, 1.0), 3)
        electrical = ElectricalStatus(
            voltage=voltage,
            current=current,
            power=round(voltage * abs(current), 3),
        )
        return evaluate(electrical, curve=self._cfg.voltage_curve)

    def _update(self) -> bool:
        """Poll hardware and update indicator. Returns True to keep timer alive."""
        self._status = self._read_status()

        # Update icon
        icon = _get_icon_name(self._status)
        self._indicator.set_icon_full(icon, "UPS battery status")

        # Update menu label
        if self._status is None and self._last_error:
            self._status_item.set_label(f"UPS: error - {self._last_error}")
        else:
            self._status_item.set_label(_format_status(self._status))

        # Check notification thresholds
        self._check_thresholds()

        return True  # keep GLib timeout active

    def _check_thresholds(self) -> None:
        """Send notifications on threshold crossings (with hysteresis)."""
        if self._status is None or self._status.percent is None:
            return

        percent = self._status.percent

        # Shutdown threshold (opt-in, triggers exactly once)
        if (
            self._cfg.shutdown_enabled
            and not self._shutdown_triggered
            and percent <= self._cfg.shutdown_percent
        ):
            self._shutdown_triggered = True
            log.critical("Shutdown threshold reached at %d%%", percent)
            self._notify(
                "UPS Shutdown",
                f"Battery at {percent}%. Initiating shutdown...",
                "system-shutdown",
                urgency=Notify.Urgency.CRITICAL,
            )
            self._execute_shutdown()

        # Critical threshold
        if percent <= self._cfg.critical_percent:
            if not self._notified_critical:
                self._notified_critical = True
                log.warning("Battery critical: %d%%", percent)
                self._notify(
                    "Battery Critical",
                    f"UPS battery at {percent}% - shutdown imminent!",
                    "battery-caution-symbolic",
                    urgency=Notify.Urgency.CRITICAL,
                )
        elif percent > self._cfg.critical_percent + 2:
            self._notified_critical = False

        # Warn threshold
        if percent <= self._cfg.warn_percent:
            if not self._notified_warn:
                self._notified_warn = True
                log.warning("Battery low: %d%%", percent)
                self._notify(
                    "Battery Low",
                    f"UPS battery at {percent}%.",
                    "battery-low-symbolic",
                    urgency=Notify.Urgency.NORMAL,
                )
        elif percent > self._cfg.warn_percent + 2:
            self._notified_warn = False

    def _notify(
        self,
        summary: str,
        body: str,
        icon: str,
        urgency: Notify.Urgency = Notify.Urgency.NORMAL,
    ) -> None:
        """Send a desktop notification."""
        n = Notify.Notification.new(summary, body, icon)
        n.set_urgency(urgency)
        try:
            n.show()
        except GLib.Error:
            pass  # Notification daemon may not be running

    def _execute_shutdown(self) -> None:
        """Execute system shutdown via systemctl."""
        try:
            subprocess.run(
                ["systemctl", "poweroff"],
                check=True,
                capture_output=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            self._notify(
                "Shutdown Failed",
                f"Could not execute shutdown: {e}",
                "dialog-error",
                urgency=Notify.Urgency.CRITICAL,
            )

    def run(self) -> None:
        """Start the indicator main loop."""
        GLib.timeout_add_seconds(self._cfg.interval, self._update)
        Gtk.main()

    def _on_quit(self, _widget: Gtk.MenuItem) -> None:
        Notify.uninit()
        Gtk.main_quit()


def _test_shutdown(cfg: Config) -> None:
    """Dry-run test of shutdown permissions and config."""
    print("=== Shutdown Dry-Run Test ===")
    print(f"  shutdown_enabled: {cfg.shutdown_enabled}")
    print(f"  shutdown_percent: {cfg.shutdown_percent}%")
    print()

    if not cfg.shutdown_enabled:
        print("Shutdown is DISABLED in config.")
        print("To enable, add to config.toml:")
        print()
        print("  [shutdown]")
        print("  enabled = true")
        print("  percent = 5")
        print()
        sys.exit(0)

    # Test if systemctl poweroff would be permitted (using --check-inhibitors only)
    print("Testing shutdown command: systemctl poweroff")
    try:
        result = subprocess.run(
            ["systemctl", "poweroff", "--when=cancel"],
            capture_output=True,
            text=True,
        )
        # --when=cancel just cancels any scheduled shutdown, harmless
        print(f"  systemctl exit code: {result.returncode}")
        if result.returncode == 0:
            print("  Result: shutdown command appears to be permitted.")
        else:
            print(f"  stderr: {result.stderr.strip()}")
            print("  Result: shutdown may require additional permissions.")
            print()
            print("To allow passwordless shutdown, add to /etc/sudoers.d/ups-shutdown:")
            user = os.environ.get("USER", "youruser")
            print(f"  {user} ALL=(ALL) NOPASSWD: /usr/bin/systemctl poweroff")
    except FileNotFoundError:
        print("  ERROR: systemctl not found on this system.")
        sys.exit(1)

    print()
    print("Dry-run complete. No shutdown was initiated.")


def main() -> None:
    parser = argparse.ArgumentParser(description="UPS HAT (B) Desktop Indicator")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config file (default: ~/.config/ups-hat-b/config.toml)",
    )
    parser.add_argument(
        "--bus",
        type=int,
        default=None,
        help="I2C bus number (overrides config/env)",
    )
    parser.add_argument(
        "--addr",
        type=lambda x: int(x, 0),
        default=None,
        help="I2C device address, e.g. 0x42 (overrides config/env)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Poll interval in seconds (overrides config)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use random mock data instead of real hardware",
    )
    parser.add_argument(
        "--test-shutdown",
        action="store_true",
        help="Test shutdown command (dry-run) and exit",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Log level (default: WARNING)",
    )
    args = parser.parse_args()

    # Configure logging to stderr (captured by journald when run as service)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )

    # Load config: file -> env -> CLI overrides
    cfg = load_config(args.config)
    if args.bus is not None:
        cfg.i2c_bus = args.bus
    if args.addr is not None:
        cfg.i2c_addr = args.addr
    if args.interval is not None:
        cfg.interval = args.interval

    # Dry-run shutdown test
    if args.test_shutdown:
        _test_shutdown(cfg)
        return

    # Allow clean exit on SIGINT/SIGTERM
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, lambda *_: Gtk.main_quit())

    indicator = UPSIndicator(cfg=cfg, mock=args.mock)
    indicator.run()


if __name__ == "__main__":
    main()
