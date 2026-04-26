"""Install bundled SVGs into the user's hicolor icon theme.

The SNI tray host on Pi OS Bookworm (`wf-panel-pi 0.102`) ignores the
`IconThemePath` SNI property and resolves `IconName` only against the
system GTK icon theme. Dropping our SVGs into
`~/.local/share/icons/hicolor/scalable/status/` makes them discoverable by
that lookup so the tray renders our actual artwork. Idempotent — files are
only copied when missing or older than the source.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

log = logging.getLogger("ups-indicator")

USER_HICOLOR_STATUS = (
    Path.home() / ".local" / "share" / "icons" / "hicolor" / "scalable" / "status"
)


def ensure_user_icons_installed(
    src_dir: Path,
    dest_dir: Path = USER_HICOLOR_STATUS,
) -> int:
    """Copy ``src_dir/*.svg`` to ``dest_dir``, skipping up-to-date files.

    Returns the number of files actually copied.
    """
    if not src_dir.is_dir():
        log.warning("Icon source directory not found: %s", src_dir)
        return 0

    dest_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for src in src_dir.glob("*.svg"):
        dest = dest_dir / src.name
        if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
            continue
        shutil.copy2(src, dest)
        copied += 1
        log.info("Installed icon %s -> %s", src.name, dest)

    return copied
