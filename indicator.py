"""UPS HAT (B) Desktop Indicator - Entry Point.

Displays UPS battery state using the best available display backend:
1. AppIndicator - system tray icon (GNOME+ext, KDE, Xfce, MATE)
2. LayerShell - floating widget for Wayland/wlroots (Pi OS Bookworm)
3. Notification - fallback using desktop notifications only
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import subprocess
import sys
from pathlib import Path

from ups.backends import detect_backend
from ups.config import load_config  # noqa: E402

log = logging.getLogger("ups-indicator")


def _test_shutdown(cfg) -> None:
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

    # Test if systemctl poweroff would be permitted
    print("Testing shutdown command: systemctl poweroff")
    try:
        result = subprocess.run(
            ["systemctl", "poweroff", "--when=cancel"],
            capture_output=True,
            text=True,
        )
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
        "--backend",
        choices=["auto", "appindicator", "layershell", "notification"],
        default="auto",
        help="Display backend (default: auto-detect)",
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

    # Detect and instantiate backend
    # Priority: CLI flag > config file > auto-detect
    if args.backend != "auto":
        preferred = args.backend
    elif cfg.backend != "auto":
        preferred = cfg.backend
    else:
        preferred = None

    try:
        backend = detect_backend(cfg, mock=args.mock, preferred=preferred)
    except RuntimeError as e:
        log.error("Backend initialization failed: %s", e)
        sys.exit(1)

    log.info("Using %s backend", backend.name)

    # Allow clean exit on SIGINT/SIGTERM
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, lambda *_: backend.stop())

    # Run the indicator
    backend.start()


if __name__ == "__main__":
    main()
