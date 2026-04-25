# UPS HAT (B) Desktop Indicator

Desktop tray indicator for the Waveshare UPS HAT (B) on Debian
GNU/Linux 12 (Bookworm) aarch64.

## Features

- Tray icon showing battery state and charge level, with a menu for
  voltage / current / power / percentage.
- Three display backends with auto-detection: **AppIndicator**
  (GNOME, KDE, Xfce, MATE), **GTK Layer Shell** widget (Pi OS
  Bookworm Wayland), and a **notification-only** fallback.
- Bundled SVG icons (white outline, Pi-OS-blue fill, red on
  critical) — render identically across icon themes and Pis.
- Mock mode (`--mock`) for testing without the HAT.
- Opt-in safe shutdown when battery drops below a configurable
  threshold.

## Quick install

On a fresh Raspberry Pi OS Bookworm (or most desktop Linux), one
line:

```bash
git clone https://github.com/JabbaghYounes/UPSentinel.git ~/UPSentinel && cd ~/UPSentinel && ./install.sh
```

If you've already cloned the repo, just run `./install.sh` from
inside it. The installer enables I2C, adds your user to the `i2c`
group, registers an autostart entry, and starts the indicator
immediately if you ran it from a desktop session. See
[docs/installation.md](docs/installation.md) for the full manual
equivalents.

## Documentation

| Topic | What's there |
|---|---|
| [Installation](docs/installation.md) | What `install.sh` does, manual install, desktop-specific tray packages |
| [Usage](docs/usage.md) | CLI flags, mock mode, environment variables, config priority |
| [Configuration](docs/configuration.md) | `config.toml` schema, voltage curve, backend pinning |
| [Autostart](docs/autostart.md) | XDG vs systemd, manual setup, auto-login, management commands |
| [Safe shutdown](docs/shutdown.md) | Enabling, polkit / sudoers permissions, dry-run verification |
| [Development](docs/development.md) | Project structure, lint, tests, architecture notes |
| [Troubleshooting](docs/troubleshooting.md) | Tray issues, I2C, notifications, wayvnc / `graphical-session.target`, logging |

## License

MIT — see [LICENSE](LICENSE) for details.
