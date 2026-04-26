"""Tests for the hicolor icon-install helper."""

from __future__ import annotations

from pathlib import Path

import pytest

from ups.icon_install import ensure_user_icons_installed


def _make_svg(path: Path, body: str = "<svg/>") -> None:
    path.write_text(body)


class TestEnsureUserIconsInstalled:
    def test_copies_missing_icons(self, tmp_path: Path) -> None:
        src = tmp_path / "icons"
        src.mkdir()
        _make_svg(src / "ups-hat-b-battery-good.svg", "<svg>good</svg>")
        _make_svg(src / "ups-hat-b-battery-low.svg", "<svg>low</svg>")
        dest = tmp_path / "hicolor" / "scalable" / "status"

        copied = ensure_user_icons_installed(src, dest)

        assert copied == 2
        assert (dest / "ups-hat-b-battery-good.svg").read_text() == "<svg>good</svg>"
        assert (dest / "ups-hat-b-battery-low.svg").read_text() == "<svg>low</svg>"

    def test_skips_up_to_date_icons(self, tmp_path: Path) -> None:
        src = tmp_path / "icons"
        src.mkdir()
        _make_svg(src / "ups-hat-b-battery-good.svg")
        dest = tmp_path / "hicolor"

        first = ensure_user_icons_installed(src, dest)
        second = ensure_user_icons_installed(src, dest)

        assert first == 1
        assert second == 0

    def test_updates_stale_icon(self, tmp_path: Path) -> None:
        src = tmp_path / "icons"
        src.mkdir()
        svg = src / "ups-hat-b-battery-good.svg"
        _make_svg(svg, "<svg>v1</svg>")
        dest = tmp_path / "hicolor"
        ensure_user_icons_installed(src, dest)

        # Bump source mtime forward and rewrite contents.
        future = svg.stat().st_mtime + 60
        _make_svg(svg, "<svg>v2</svg>")
        import os

        os.utime(svg, (future, future))

        copied = ensure_user_icons_installed(src, dest)
        assert copied == 1
        assert (dest / "ups-hat-b-battery-good.svg").read_text() == "<svg>v2</svg>"

    def test_creates_dest_dir(self, tmp_path: Path) -> None:
        src = tmp_path / "icons"
        src.mkdir()
        _make_svg(src / "ups-hat-b-battery-good.svg")
        dest = tmp_path / "deep" / "nested" / "hicolor"
        assert not dest.exists()

        ensure_user_icons_installed(src, dest)

        assert dest.is_dir()
        assert (dest / "ups-hat-b-battery-good.svg").is_file()

    def test_missing_source_dir_is_noop(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        src = tmp_path / "does-not-exist"
        dest = tmp_path / "hicolor"

        copied = ensure_user_icons_installed(src, dest)
        assert copied == 0
        assert not dest.exists()

    def test_only_svg_files_are_copied(self, tmp_path: Path) -> None:
        src = tmp_path / "icons"
        src.mkdir()
        _make_svg(src / "ups-hat-b-battery-good.svg")
        (src / "README.md").write_text("docs")
        (src / "battery.png").write_bytes(b"PNG")
        dest = tmp_path / "hicolor"

        copied = ensure_user_icons_installed(src, dest)
        assert copied == 1
        assert sorted(p.name for p in dest.iterdir()) == ["ups-hat-b-battery-good.svg"]
