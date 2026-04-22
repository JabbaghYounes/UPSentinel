"""AppIndicator backend for system tray display.

Works on desktops with AppIndicator/StatusNotifierItem support:
- GNOME (with gnome-shell-extension-appindicator)
- KDE Plasma
- Xfce (with xfce4-indicator-plugin)
- MATE (with mate-indicator-applet)
"""

from __future__ import annotations

import logging

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")

from gi.repository import AyatanaAppIndicator3 as AppIndicator3  # noqa: E402
from gi.repository import GLib, Gtk  # noqa: E402

from ups.backends import (  # noqa: E402
    ICON_DEFAULT,
    StatusBackend,
    format_status,
    get_icon_name,
)
from ups.config import Config  # noqa: E402
from ups.model import UPSStatus  # noqa: E402

log = logging.getLogger("ups-indicator")


class AppIndicatorBackend(StatusBackend):
    """System tray indicator using Ayatana AppIndicator."""

    def __init__(self, cfg: Config, mock: bool = False) -> None:
        super().__init__(cfg, mock)

        self._indicator = AppIndicator3.Indicator.new(
            "ups-hat-b-indicator",
            ICON_DEFAULT,
            AppIndicator3.IndicatorCategory.HARDWARE,
        )
        self._indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

        log.info(
            "Starting AppIndicator backend: bus=%d addr=0x%02X interval=%ds mock=%s",
            cfg.i2c_bus, cfg.i2c_addr, cfg.interval, mock,
        )

        self._build_menu()
        # Initial poll
        self.poll()

    @property
    def name(self) -> str:
        return "appindicator"

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

    def update_display(self, status: UPSStatus | None) -> None:
        """Update the tray icon and menu label."""
        # Update icon
        icon = get_icon_name(status)
        self._indicator.set_icon_full(icon, "UPS battery status")

        # Update menu label
        if status is None and self._last_error:
            self._status_item.set_label(f"UPS: error - {self._last_error}")
        else:
            self._status_item.set_label(format_status(status))

    def start(self) -> None:
        """Start the GTK main loop with polling."""
        GLib.timeout_add_seconds(self.cfg.interval, self.poll)
        Gtk.main()

    def stop(self) -> None:
        """Stop the GTK main loop."""
        self.cleanup()
        Gtk.main_quit()

    def _on_quit(self, _widget: Gtk.MenuItem) -> None:
        self.stop()
