"""Display backends for UPS status indicator.

Provides multiple UI backends with automatic detection:
1. AppIndicator - system tray icon (GNOME+ext, KDE, Xfce, MATE)
2. LayerShell - floating widget for Wayland/wlroots (Pi OS Bookworm)
3. Notification - fallback using desktop notifications only
"""

from __future__ import annotations

import logging
import os
import random
import subprocess
from abc import ABC, abstractmethod

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Notify", "0.7")

from gi.repository import GLib, Notify  # noqa: E402

from ups.battery import evaluate  # noqa: E402
from ups.config import Config  # noqa: E402
from ups.hardware import I2CError, read_electrical_status  # noqa: E402
from ups.model import BatteryState, ElectricalStatus, UPSStatus  # noqa: E402

log = logging.getLogger("ups-indicator")

# Number of consecutive read failures before notifying
ERROR_NOTIFY_THRESHOLD = 3

# Icon name mapping: (min_percent, max_percent) -> icon_name
ICON_MAP: list[tuple[int, int, str, str]] = [
    # (min%, max%, discharging_icon, charging_icon)
    (0, 10, "battery-caution-symbolic", "battery-caution-charging-symbolic"),
    (11, 20, "battery-low-symbolic", "battery-low-charging-symbolic"),
    (21, 50, "battery-low-symbolic", "battery-good-charging-symbolic"),
    (51, 80, "battery-good-symbolic", "battery-good-charging-symbolic"),
    (81, 100, "battery-full-symbolic", "battery-full-charging-symbolic"),
]

ICON_MISSING = "battery-missing-symbolic"
ICON_DEFAULT = "battery-good-symbolic"

APP_NAME = "UPS HAT (B)"


def get_icon_name(status: UPSStatus | None) -> str:
    """Select an icon name based on UPS status."""
    if status is None or status.percent is None:
        return ICON_MISSING

    charging = status.state == BatteryState.CHARGING

    for min_pct, max_pct, discharge_icon, charge_icon in ICON_MAP:
        if min_pct <= status.percent <= max_pct:
            return charge_icon if charging else discharge_icon

    return ICON_DEFAULT


def format_status(status: UPSStatus | None) -> str:
    """Format status for display in menu."""
    if status is None:
        return "UPS: unavailable"

    pct = f"{status.percent}%" if status.percent is not None else "?%"
    return (
        f"{pct}  |  {status.voltage:.2f}V  "
        f"{status.current:.3f}A  {status.power:.2f}W  "
        f"[{status.state.value}]"
    )


class StatusBackend(ABC):
    """Base class for status display backends with shared functionality."""

    def __init__(self, cfg: Config, mock: bool = False) -> None:
        self.cfg = cfg
        self.mock = mock
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

        # Initialize notifications
        Notify.init(APP_NAME)

    @abstractmethod
    def start(self) -> None:
        """Start the backend main loop."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop the backend and clean up."""
        ...

    @abstractmethod
    def update_display(self, status: UPSStatus | None) -> None:
        """Update the backend-specific display. Called after reading status."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the backend name for logging."""
        ...

    def read_status(self) -> UPSStatus | None:
        """Read UPS status from hardware or mock."""
        if self.mock:
            return self._mock_status()
        try:
            data = read_electrical_status(
                bus_num=self.cfg.i2c_bus,
                addr=self.cfg.i2c_addr,
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
            status = evaluate(electrical, curve=self.cfg.voltage_curve)
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

    def _mock_status(self) -> UPSStatus:
        """Generate a mock UPS status for testing."""
        voltage = round(random.uniform(6.0, 8.4), 2)
        current = round(random.uniform(-1.0, 1.0), 3)
        electrical = ElectricalStatus(
            voltage=voltage,
            current=current,
            power=round(voltage * abs(current), 3),
        )
        return evaluate(electrical, curve=self.cfg.voltage_curve)

    def _handle_error(self) -> None:
        """Handle read failures: notify after repeated errors."""
        if (
            self._consecutive_failures >= ERROR_NOTIFY_THRESHOLD
            and not self._error_notified
        ):
            self._error_notified = True
            self.notify(
                "UPS Read Error",
                f"Cannot read UPS after {self._consecutive_failures} attempts.\n"
                f"{self._last_error}",
                "dialog-warning",
            )

    def poll(self) -> bool:
        """Poll hardware and update display. Returns True to keep timer alive."""
        self._status = self.read_status()
        self.update_display(self._status)
        self.check_thresholds()
        return True

    def check_thresholds(self) -> None:
        """Send notifications on threshold crossings (with hysteresis)."""
        if self._status is None or self._status.percent is None:
            return

        percent = self._status.percent

        # Shutdown threshold (opt-in, triggers exactly once)
        if (
            self.cfg.shutdown_enabled
            and not self._shutdown_triggered
            and percent <= self.cfg.shutdown_percent
        ):
            self._shutdown_triggered = True
            log.critical("Shutdown threshold reached at %d%%", percent)
            self.notify(
                "UPS Shutdown",
                f"Battery at {percent}%. Initiating shutdown...",
                "system-shutdown",
                urgency=Notify.Urgency.CRITICAL,
            )
            self._execute_shutdown()

        # Critical threshold
        if percent <= self.cfg.critical_percent:
            if not self._notified_critical:
                self._notified_critical = True
                log.warning("Battery critical: %d%%", percent)
                self.notify(
                    "Battery Critical",
                    f"UPS battery at {percent}% - shutdown imminent!",
                    "battery-caution-symbolic",
                    urgency=Notify.Urgency.CRITICAL,
                )
        elif percent > self.cfg.critical_percent + 2:
            self._notified_critical = False

        # Warn threshold
        if percent <= self.cfg.warn_percent:
            if not self._notified_warn:
                self._notified_warn = True
                log.warning("Battery low: %d%%", percent)
                self.notify(
                    "Battery Low",
                    f"UPS battery at {percent}%.",
                    "battery-low-symbolic",
                    urgency=Notify.Urgency.NORMAL,
                )
        elif percent > self.cfg.warn_percent + 2:
            self._notified_warn = False

    def notify(
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
            self.notify(
                "Shutdown Failed",
                f"Could not execute shutdown: {e}",
                "dialog-error",
                urgency=Notify.Urgency.CRITICAL,
            )

    def cleanup(self) -> None:
        """Clean up resources."""
        Notify.uninit()


def is_wayland() -> bool:
    """Check if running under a Wayland session."""
    return os.environ.get("XDG_SESSION_TYPE") == "wayland"


def appindicator_available() -> bool:
    """Check if AppIndicator library is available."""
    try:
        import gi
        gi.require_version("AyatanaAppIndicator3", "0.1")
        from gi.repository import AyatanaAppIndicator3  # noqa: F401
        return True
    except (ValueError, ImportError):
        return False


def layer_shell_available() -> bool:
    """Check if GTK Layer Shell is available."""
    try:
        import gi
        gi.require_version("GtkLayerShell", "0.1")
        from gi.repository import GtkLayerShell  # noqa: F401
        return True
    except (ValueError, ImportError):
        return False


def detect_backend(
    cfg: Config,
    mock: bool = False,
    preferred: str | None = None,
) -> StatusBackend:
    """Detect and instantiate the best available backend.

    Args:
        cfg: Application configuration.
        mock: Whether to use mock data.
        preferred: Preferred backend name ('appindicator', 'layershell', 'notification')
                   or None/'auto' for automatic detection.

    Returns:
        Instantiated StatusBackend.

    Raises:
        RuntimeError: If the preferred backend is not available.
    """
    # Handle explicit backend selection
    if preferred and preferred != "auto":
        if preferred == "appindicator":
            if not appindicator_available():
                raise RuntimeError(
                    "AppIndicator backend requested but gir1.2-ayatanaappindicator3-0.1 "
                    "is not installed"
                )
            from ups.backends.appindicator import AppIndicatorBackend
            log.info("Using AppIndicator backend (forced)")
            return AppIndicatorBackend(cfg, mock)

        elif preferred == "layershell":
            if not layer_shell_available():
                raise RuntimeError(
                    "LayerShell backend requested but gir1.2-gtklayershell-0.1 "
                    "is not installed"
                )
            from ups.backends.layershell import LayerShellBackend
            log.info("Using LayerShell backend (forced)")
            return LayerShellBackend(cfg, mock)

        elif preferred == "notification":
            from ups.backends.notification import NotificationBackend
            log.info("Using Notification backend (forced)")
            return NotificationBackend(cfg, mock)

        else:
            raise RuntimeError(f"Unknown backend: {preferred}")

    # Auto-detection
    # 1. Try AppIndicator first (most feature-rich)
    if appindicator_available():
        from ups.backends.appindicator import AppIndicatorBackend
        log.info("Using AppIndicator backend (auto-detected)")
        return AppIndicatorBackend(cfg, mock)

    # 2. Try Layer Shell for Wayland
    if is_wayland() and layer_shell_available():
        from ups.backends.layershell import LayerShellBackend
        log.info("Using LayerShell backend (auto-detected, Wayland session)")
        return LayerShellBackend(cfg, mock)

    # 3. Fallback to notifications
    from ups.backends.notification import NotificationBackend
    log.warning(
        "No tray/widget backend available, falling back to notification-only mode"
    )
    return NotificationBackend(cfg, mock)


__all__ = [
    "StatusBackend",
    "detect_backend",
    "is_wayland",
    "appindicator_available",
    "layer_shell_available",
]
