"""Notification-only backend as a universal fallback.

This backend has no persistent UI - it only sends desktop notifications
for status updates and alerts. Used when neither AppIndicator nor
Layer Shell are available.
"""

from __future__ import annotations

import logging

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Notify", "0.7")

from gi.repository import GLib, Gtk, Notify  # noqa: E402

from ups.backends import StatusBackend, get_icon_name  # noqa: E402
from ups.config import Config  # noqa: E402
from ups.model import BatteryState, UPSStatus  # noqa: E402

log = logging.getLogger("ups-indicator")


class NotificationBackend(StatusBackend):
    """Notification-only backend with no persistent display."""

    def __init__(self, cfg: Config, mock: bool = False) -> None:
        super().__init__(cfg, mock)

        log.info(
            "Starting Notification backend: bus=%d addr=0x%02X interval=%ds mock=%s",
            cfg.i2c_bus, cfg.i2c_addr, cfg.interval, mock,
        )

        # Track last notified percentage to avoid spam
        self._last_notified_percent: int | None = None

        # Counter for periodic status updates
        self._poll_count = 0

        # Initial poll
        self.poll()

    @property
    def name(self) -> str:
        return "notification"

    def update_display(self, status: UPSStatus | None) -> None:
        """Send periodic status notifications.

        Unlike tray backends, we don't have a persistent display,
        so we send periodic notifications:
        - Every 10 polls at normal battery levels
        - Every 5 polls below warn threshold
        - Every poll below critical threshold
        """
        self._poll_count += 1

        if status is None:
            # Error state - handled by base class _handle_error
            return

        percent = status.percent
        if percent is None:
            return

        # Determine notification frequency based on battery level
        if percent <= self.cfg.critical_percent:
            notify_interval = 1  # Every poll
        elif percent <= self.cfg.warn_percent:
            notify_interval = 5  # Every 5 polls
        else:
            notify_interval = 10  # Every 10 polls (roughly every minute at 5s interval)

        # Send periodic status notification
        if self._poll_count % notify_interval == 0:
            self._send_status_notification(status)
            self._last_notified_percent = percent

    def _send_status_notification(self, status: UPSStatus) -> None:
        """Send a status notification."""
        if status.percent is None:
            return

        icon = get_icon_name(status)

        # Build status message
        if status.state == BatteryState.CHARGING:
            state_str = "Charging"
        elif status.state == BatteryState.DISCHARGING:
            state_str = "Discharging"
        else:
            state_str = "Unknown"

        body = (
            f"{status.voltage:.2f}V  |  {status.current:.3f}A  |  {status.power:.2f}W\n"
            f"State: {state_str}"
        )

        # Choose urgency
        if status.percent <= self.cfg.critical_percent:
            urgency = Notify.Urgency.CRITICAL
            title = f"UPS Battery: {status.percent}% ⚠️"
        elif status.percent <= self.cfg.warn_percent:
            urgency = Notify.Urgency.NORMAL
            title = f"UPS Battery: {status.percent}%"
        else:
            urgency = Notify.Urgency.LOW
            title = f"UPS Battery: {status.percent}%"

        n = Notify.Notification.new(title, body, icon)
        n.set_urgency(urgency)
        try:
            n.show()
        except GLib.Error:
            pass

    def start(self) -> None:
        """Start the GTK main loop with polling."""
        # Send initial notification
        if self._status is not None:
            self._send_status_notification(self._status)

        log.info(
            "Notification backend started - no tray icon, status via notifications only"
        )

        GLib.timeout_add_seconds(self.cfg.interval, self.poll)
        Gtk.main()

    def stop(self) -> None:
        """Stop the GTK main loop."""
        self.cleanup()
        Gtk.main_quit()
