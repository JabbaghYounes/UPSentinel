"""GTK Layer Shell backend for Wayland compositors.

Works on wlroots-based compositors like Wayfire (Pi OS Bookworm default),
Sway, and Hyprland. Creates a small floating widget in the corner.
"""

from __future__ import annotations

import logging

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")

from gi.repository import Gdk, GLib, Gtk, GtkLayerShell  # noqa: E402

from ups.backends import (  # noqa: E402
    ICON_DEFAULT,
    ICON_MISSING,
    StatusBackend,
    format_status,
    get_icon_name,
)
from ups.config import Config  # noqa: E402
from ups.model import BatteryState, UPSStatus  # noqa: E402

log = logging.getLogger("ups-indicator")

# Widget styling
_CSS = b"""
.ups-widget {
    background-color: rgba(40, 40, 40, 0.9);
    border-radius: 8px;
    padding: 4px 8px;
    color: #ffffff;
    font-size: 12px;
}
.ups-widget:hover {
    background-color: rgba(60, 60, 60, 0.95);
}
.ups-percent {
    font-weight: bold;
    font-size: 13px;
}
.ups-charging {
    color: #73d216;
}
.ups-discharging {
    color: #f57900;
}
.ups-critical {
    color: #ef2929;
}
.ups-menu {
    background-color: rgba(50, 50, 50, 0.95);
    border-radius: 6px;
    padding: 8px;
}
"""


class LayerShellBackend(StatusBackend):
    """Floating corner widget using GTK Layer Shell for Wayland."""

    def __init__(self, cfg: Config, mock: bool = False) -> None:
        super().__init__(cfg, mock)

        log.info(
            "Starting LayerShell backend: bus=%d addr=0x%02X interval=%ds mock=%s",
            cfg.i2c_bus, cfg.i2c_addr, cfg.interval, mock,
        )

        self._setup_css()
        self._create_widget()
        self._create_menu()

        # Initial poll
        self.poll()

    @property
    def name(self) -> str:
        return "layershell"

    def _setup_css(self) -> None:
        """Load CSS styling for the widget."""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(_CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _create_widget(self) -> None:
        """Create the floating status widget."""
        self._window = Gtk.Window()

        # Initialize Layer Shell
        GtkLayerShell.init_for_window(self._window)
        GtkLayerShell.set_layer(self._window, GtkLayerShell.Layer.TOP)

        # Anchor to top-right corner
        GtkLayerShell.set_anchor(self._window, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self._window, GtkLayerShell.Edge.RIGHT, True)

        # Margins from edges
        GtkLayerShell.set_margin(self._window, GtkLayerShell.Edge.TOP, 8)
        GtkLayerShell.set_margin(self._window, GtkLayerShell.Edge.RIGHT, 8)

        # Create content box
        event_box = Gtk.EventBox()
        event_box.connect("button-press-event", self._on_click)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.get_style_context().add_class("ups-widget")

        # Battery icon
        self._icon = Gtk.Image.new_from_icon_name(ICON_DEFAULT, Gtk.IconSize.MENU)
        box.pack_start(self._icon, False, False, 0)

        # Percentage label
        self._label = Gtk.Label(label="---%")
        self._label.get_style_context().add_class("ups-percent")
        box.pack_start(self._label, False, False, 0)

        # State indicator (charging symbol)
        self._state_label = Gtk.Label(label="")
        box.pack_start(self._state_label, False, False, 0)

        event_box.add(box)
        self._window.add(event_box)

    def _create_menu(self) -> None:
        """Create the popup menu for detailed status."""
        self._menu = Gtk.Menu()
        self._menu.get_style_context().add_class("ups-menu")

        # Status details (non-interactive)
        self._menu_status = Gtk.MenuItem(label="UPS: reading...")
        self._menu_status.set_sensitive(False)
        self._menu.append(self._menu_status)

        self._menu.append(Gtk.SeparatorMenuItem())

        # Voltage
        self._menu_voltage = Gtk.MenuItem(label="Voltage: ---")
        self._menu_voltage.set_sensitive(False)
        self._menu.append(self._menu_voltage)

        # Current
        self._menu_current = Gtk.MenuItem(label="Current: ---")
        self._menu_current.set_sensitive(False)
        self._menu.append(self._menu_current)

        # Power
        self._menu_power = Gtk.MenuItem(label="Power: ---")
        self._menu_power.set_sensitive(False)
        self._menu.append(self._menu_power)

        self._menu.append(Gtk.SeparatorMenuItem())

        # Quit
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self._on_quit)
        self._menu.append(quit_item)

        self._menu.show_all()

    def _on_click(self, widget: Gtk.Widget, event: Gdk.EventButton) -> bool:
        """Handle click on widget to show menu."""
        if event.button == 1:  # Left click
            self._menu.popup_at_widget(
                widget,
                Gdk.Gravity.SOUTH_EAST,
                Gdk.Gravity.NORTH_EAST,
                event,
            )
            return True
        elif event.button == 3:  # Right click
            self._menu.popup_at_widget(
                widget,
                Gdk.Gravity.SOUTH_EAST,
                Gdk.Gravity.NORTH_EAST,
                event,
            )
            return True
        return False

    def update_display(self, status: UPSStatus | None) -> None:
        """Update the widget and menu with current status."""
        if status is None:
            self._icon.set_from_icon_name(ICON_MISSING, Gtk.IconSize.MENU)
            self._label.set_text("ERR")
            self._label.get_style_context().remove_class("ups-charging")
            self._label.get_style_context().remove_class("ups-discharging")
            self._label.get_style_context().add_class("ups-critical")
            self._state_label.set_text("")
            self._menu_status.set_label(f"UPS: error - {self._last_error}")
            self._menu_voltage.set_label("Voltage: ---")
            self._menu_current.set_label("Current: ---")
            self._menu_power.set_label("Power: ---")
            return

        # Update icon (bundled SVG, absolute path)
        icon_path = get_icon_name(status)
        self._icon.set_from_file(icon_path)

        # Update percentage label
        pct = f"{status.percent}%" if status.percent is not None else "?%"
        self._label.set_text(pct)

        # Update styling based on state
        ctx = self._label.get_style_context()
        ctx.remove_class("ups-charging")
        ctx.remove_class("ups-discharging")
        ctx.remove_class("ups-critical")

        if status.percent is not None and status.percent <= self.cfg.critical_percent:
            ctx.add_class("ups-critical")
        elif status.state == BatteryState.CHARGING:
            ctx.add_class("ups-charging")
        elif status.state == BatteryState.DISCHARGING:
            ctx.add_class("ups-discharging")

        # Update state indicator
        if status.state == BatteryState.CHARGING:
            self._state_label.set_text("⚡")
        elif status.state == BatteryState.DISCHARGING:
            self._state_label.set_text("🔋")
        else:
            self._state_label.set_text("")

        # Update menu
        self._menu_status.set_label(format_status(status))
        self._menu_voltage.set_label(f"Voltage: {status.voltage:.2f} V")
        self._menu_current.set_label(f"Current: {status.current:.3f} A")
        self._menu_power.set_label(f"Power: {status.power:.2f} W")

    def start(self) -> None:
        """Start the GTK main loop with polling."""
        self._window.show_all()
        GLib.timeout_add_seconds(self.cfg.interval, self.poll)
        Gtk.main()

    def stop(self) -> None:
        """Stop the GTK main loop and cleanup."""
        self.cleanup()
        self._window.destroy()
        Gtk.main_quit()

    def _on_quit(self, _widget: Gtk.MenuItem) -> None:
        self.stop()
