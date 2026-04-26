"""AppIndicator backend for system tray display.

Works on desktops with AppIndicator/StatusNotifierItem support:
- GNOME (with gnome-shell-extension-appindicator)
- KDE Plasma
- Xfce (with xfce4-indicator-plugin)
- MATE (with mate-indicator-applet)
"""

from __future__ import annotations

import logging
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")

from gi.repository import AyatanaAppIndicator3 as AppIndicator3  # noqa: E402
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from ups.backends import (  # noqa: E402
    ICON_DEFAULT,
    ICONS_DIR,
    StatusBackend,
    format_status,
    get_icon_name,
)
from ups.config import Config  # noqa: E402
from ups.icon_install import ensure_user_icons_installed  # noqa: E402
from ups.model import UPSStatus  # noqa: E402

log = logging.getLogger("ups-indicator")


class AppIndicatorBackend(StatusBackend):
    """System tray indicator using Ayatana AppIndicator."""

    def __init__(self, cfg: Config, mock: bool = False) -> None:
        super().__init__(cfg, mock)

        log.info(
            "Starting AppIndicator backend: bus=%d addr=0x%02X interval=%ds mock=%s",
            cfg.i2c_bus, cfg.i2c_addr, cfg.interval, mock,
        )

        # SNI hosts (e.g. wf-panel-pi 0.102) ignore IconThemePath and only
        # resolve IconName via the system GTK icon theme. Drop our SVGs into
        # the user's hicolor theme so theme-name lookup finds them.
        ensure_user_icons_installed(ICONS_DIR)

        self._indicator: AppIndicator3.Indicator | None = None
        self._status_item: Gtk.MenuItem | None = None
        self._create_indicator()

        # Initial poll
        self.poll()

        # The StatusNotifierWatcher (e.g. wf-panel-pi's tray) can restart
        # mid-session; libayatana doesn't re-register on its own, so the icon
        # silently disappears. Watch the well-known bus name and toggle
        # status PASSIVE -> ACTIVE when it returns to force re-registration.
        self._needs_reregister = False
        self._watcher_id = Gio.bus_watch_name(
            Gio.BusType.SESSION,
            "org.kde.StatusNotifierWatcher",
            Gio.BusNameWatcherFlags.NONE,
            self._on_watcher_appeared,
            self._on_watcher_vanished,
        )

    @property
    def name(self) -> str:
        return "appindicator"

    def _create_indicator(self) -> None:
        """Construct the AppIndicator and its menu."""
        self._indicator = AppIndicator3.Indicator.new(
            "ups-hat-b-indicator",
            Path(ICON_DEFAULT).stem,
            AppIndicator3.IndicatorCategory.HARDWARE,
        )
        self._indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self._build_menu()

    def _on_watcher_vanished(self, _conn: object, _name: str) -> None:
        log.warning(
            "StatusNotifierWatcher vanished; tray icon will reappear when the host restarts"
        )
        self._needs_reregister = True

    def _on_watcher_appeared(self, _conn: object, _name: str, _owner: str) -> None:
        if not self._needs_reregister:
            # First fire at startup — indicator already exists.
            return
        log.info("StatusNotifierWatcher reappeared; re-registering indicator")
        if self._indicator is not None:
            # Toggling status forces libayatana to call RegisterStatusNotifierItem
            # against the new watcher. Recreating the indicator would conflict
            # with the old object's still-live D-Bus exports at the same path.
            self._indicator.set_status(AppIndicator3.IndicatorStatus.PASSIVE)
            self._indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
            self.update_display(self._status)
        self._needs_reregister = False

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
        # get_icon_name returns an absolute path; SNI wants the basename.
        icon = Path(get_icon_name(status)).stem
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
        if self._watcher_id:
            Gio.bus_unwatch_name(self._watcher_id)
            self._watcher_id = 0
        self.cleanup()
        Gtk.main_quit()

    def _on_quit(self, _widget: Gtk.MenuItem) -> None:
        self.stop()
