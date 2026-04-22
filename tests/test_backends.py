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
