"""Tests for display backend detection and base functionality."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ups.backends import (
    appindicator_available,
    detect_backend,
    is_wayland,
    layer_shell_available,
)
from ups.config import Config


class TestDetectionFunctions:
    """Tests for backend availability detection functions."""

    def test_is_wayland_returns_bool(self) -> None:
        result = is_wayland()
        assert isinstance(result, bool)

    def test_is_wayland_with_wayland_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        assert is_wayland() is True

    def test_is_wayland_with_x11_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
        assert is_wayland() is False

    def test_is_wayland_with_no_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
        assert is_wayland() is False

    def test_appindicator_available_returns_bool(self) -> None:
        result = appindicator_available()
        assert isinstance(result, bool)

    def test_layer_shell_available_returns_bool(self) -> None:
        result = layer_shell_available()
        assert isinstance(result, bool)


class TestDetectBackend:
    """Tests for backend auto-detection logic."""

    @patch("ups.backends.appindicator_available")
    def test_auto_uses_appindicator_when_available(
        self, mock_appindicator: MagicMock
    ) -> None:
        mock_appindicator.return_value = True
        cfg = Config()
        backend = detect_backend(cfg, mock=True)
        assert backend.name == "appindicator"

    @pytest.mark.skipif(
        not layer_shell_available(),
        reason="GtkLayerShell not installed"
    )
    @patch("ups.backends.appindicator_available")
    @patch("ups.backends.is_wayland")
    def test_auto_uses_layershell_on_wayland(
        self,
        mock_wayland: MagicMock,
        mock_appindicator: MagicMock,
    ) -> None:
        mock_appindicator.return_value = False
        mock_wayland.return_value = True
        cfg = Config()
        backend = detect_backend(cfg, mock=True)
        assert backend.name == "layershell"

    @patch("ups.backends.appindicator_available")
    @patch("ups.backends.layer_shell_available")
    def test_auto_falls_back_to_notification(
        self,
        mock_layer: MagicMock,
        mock_appindicator: MagicMock,
    ) -> None:
        mock_appindicator.return_value = False
        mock_layer.return_value = False
        cfg = Config()
        backend = detect_backend(cfg, mock=True)
        assert backend.name == "notification"

    @patch("ups.backends.appindicator_available")
    def test_forced_appindicator(self, mock_appindicator: MagicMock) -> None:
        mock_appindicator.return_value = True
        cfg = Config()
        backend = detect_backend(cfg, mock=True, preferred="appindicator")
        assert backend.name == "appindicator"

    @patch("ups.backends.appindicator_available")
    def test_forced_appindicator_unavailable_raises(
        self, mock_appindicator: MagicMock
    ) -> None:
        mock_appindicator.return_value = False
        cfg = Config()
        with pytest.raises(RuntimeError, match="AppIndicator backend requested"):
            detect_backend(cfg, mock=True, preferred="appindicator")

    @patch("ups.backends.layer_shell_available")
    def test_forced_layershell_unavailable_raises(
        self, mock_layer: MagicMock
    ) -> None:
        mock_layer.return_value = False
        cfg = Config()
        with pytest.raises(RuntimeError, match="LayerShell backend requested"):
            detect_backend(cfg, mock=True, preferred="layershell")

    def test_forced_notification_always_works(self) -> None:
        cfg = Config()
        backend = detect_backend(cfg, mock=True, preferred="notification")
        assert backend.name == "notification"

    def test_unknown_backend_raises(self) -> None:
        cfg = Config()
        with pytest.raises(RuntimeError, match="Unknown backend"):
            detect_backend(cfg, mock=True, preferred="invalid")


class TestStatusBackendBase:
    """Tests for StatusBackend base class functionality."""

    @patch("ups.backends.appindicator_available")
    def test_backend_has_config(self, mock_appindicator: MagicMock) -> None:
        mock_appindicator.return_value = True
        cfg = Config(interval=10, warn_percent=25)
        backend = detect_backend(cfg, mock=True)
        assert backend.cfg.interval == 10
        assert backend.cfg.warn_percent == 25

    @patch("ups.backends.appindicator_available")
    def test_backend_mock_mode(self, mock_appindicator: MagicMock) -> None:
        mock_appindicator.return_value = True
        cfg = Config()
        backend = detect_backend(cfg, mock=True)
        assert backend.mock is True

        backend2 = detect_backend(cfg, mock=False)
        assert backend2.mock is False

    @patch("ups.backends.appindicator_available")
    def test_backend_read_status_mock(self, mock_appindicator: MagicMock) -> None:
        mock_appindicator.return_value = True
        cfg = Config()
        backend = detect_backend(cfg, mock=True)

        status = backend.read_status()
        assert status is not None
        assert status.voltage > 0
        assert status.percent is not None
        assert 0 <= status.percent <= 100


class TestConfigBackendOption:
    """Tests for backend option in config."""

    def test_default_backend_is_auto(self) -> None:
        cfg = Config()
        assert cfg.backend == "auto"

    def test_config_accepts_valid_backends(self) -> None:
        for backend in ["auto", "appindicator", "layershell", "notification"]:
            cfg = Config(backend=backend)
            assert cfg.backend == backend


@pytest.mark.skipif(
    not appindicator_available(),
    reason="AyatanaAppIndicator3 not installed",
)
class TestAppIndicatorReconnect:
    """Re-register the AppIndicator with the SNI watcher when the host
    (e.g. wf-panel-pi) restarts.

    Without this, libayatana never re-registers and the tray icon stays
    invisible for the rest of the process's life. We re-register by
    toggling status PASSIVE -> ACTIVE on the existing indicator, because
    constructing a new ``Indicator`` collides with the still-live D-Bus
    exports at the same object path.
    """

    @pytest.fixture(autouse=True)
    def _no_icon_install(self):
        from ups.backends import appindicator as ai_mod

        with patch.object(ai_mod, "ensure_user_icons_installed", return_value=0):
            yield

    def test_initial_construction(self) -> None:
        from ups.backends import appindicator as ai_mod

        with patch.object(ai_mod.AppIndicator3.Indicator, "new") as new_mock, \
                patch.object(ai_mod.Gio, "bus_watch_name", return_value=42):
            new_mock.return_value = MagicMock()
            backend = ai_mod.AppIndicatorBackend(Config(), mock=True)
            assert new_mock.call_count == 1
            assert backend._needs_reregister is False
            assert backend._watcher_id == 42

    def test_vanished_then_appeared_reregisters(self) -> None:
        from ups.backends import appindicator as ai_mod

        captured: dict = {}

        def fake_watch(_bus, _name, _flags, on_appeared, on_vanished):
            captured["appeared"] = on_appeared
            captured["vanished"] = on_vanished
            return 7

        with patch.object(ai_mod.AppIndicator3.Indicator, "new") as new_mock, \
                patch.object(ai_mod.Gio, "bus_watch_name", side_effect=fake_watch):
            indicator_mock = MagicMock()
            new_mock.return_value = indicator_mock
            backend = ai_mod.AppIndicatorBackend(Config(), mock=True)
            assert new_mock.call_count == 1
            indicator_mock.set_status.reset_mock()

            captured["vanished"](None, "org.kde.StatusNotifierWatcher")
            assert backend._needs_reregister is True
            indicator_mock.set_status.assert_not_called()

            captured["appeared"](None, "org.kde.StatusNotifierWatcher", ":1.99")
            # No new Indicator constructed — the old one is reused.
            assert new_mock.call_count == 1
            # Status was toggled PASSIVE -> ACTIVE to force re-registration.
            statuses = [c.args[0] for c in indicator_mock.set_status.call_args_list]
            assert statuses == [
                ai_mod.AppIndicator3.IndicatorStatus.PASSIVE,
                ai_mod.AppIndicator3.IndicatorStatus.ACTIVE,
            ]
            assert backend._needs_reregister is False

    def test_appeared_at_startup_is_noop(self) -> None:
        from ups.backends import appindicator as ai_mod

        captured: dict = {}

        def fake_watch(_bus, _name, _flags, on_appeared, on_vanished):
            captured["appeared"] = on_appeared
            return 1

        with patch.object(ai_mod.AppIndicator3.Indicator, "new") as new_mock, \
                patch.object(ai_mod.Gio, "bus_watch_name", side_effect=fake_watch):
            indicator_mock = MagicMock()
            new_mock.return_value = indicator_mock
            ai_mod.AppIndicatorBackend(Config(), mock=True)
            indicator_mock.set_status.reset_mock()

            # The watcher's first "appeared" callback fires when the existing
            # SNI host is already up — must not trigger any re-register work.
            captured["appeared"](None, "org.kde.StatusNotifierWatcher", ":1.42")
            assert new_mock.call_count == 1
            indicator_mock.set_status.assert_not_called()

    def test_repeated_appeared_without_vanish_is_noop(self) -> None:
        from ups.backends import appindicator as ai_mod

        captured: dict = {}

        def fake_watch(_bus, _name, _flags, on_appeared, on_vanished):
            captured["appeared"] = on_appeared
            captured["vanished"] = on_vanished
            return 1

        with patch.object(ai_mod.AppIndicator3.Indicator, "new") as new_mock, \
                patch.object(ai_mod.Gio, "bus_watch_name", side_effect=fake_watch):
            indicator_mock = MagicMock()
            new_mock.return_value = indicator_mock
            ai_mod.AppIndicatorBackend(Config(), mock=True)

            captured["vanished"](None, "org.kde.StatusNotifierWatcher")
            captured["appeared"](None, "org.kde.StatusNotifierWatcher", ":1.99")
            indicator_mock.set_status.reset_mock()
            captured["appeared"](None, "org.kde.StatusNotifierWatcher", ":1.99")
            indicator_mock.set_status.assert_not_called()  # no vanish in between

    def test_stop_unwatches(self) -> None:
        from ups.backends import appindicator as ai_mod

        with patch.object(ai_mod.AppIndicator3.Indicator, "new") as new_mock, \
                patch.object(ai_mod.Gio, "bus_watch_name", return_value=99), \
                patch.object(ai_mod.Gio, "bus_unwatch_name") as unwatch_mock, \
                patch.object(ai_mod.Gtk, "main_quit"):
            new_mock.return_value = MagicMock()
            backend = ai_mod.AppIndicatorBackend(Config(), mock=True)
            backend.stop()
            unwatch_mock.assert_called_once_with(99)
            assert backend._watcher_id == 0
