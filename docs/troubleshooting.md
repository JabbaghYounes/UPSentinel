# Troubleshooting

## Icon not visible in system tray

- **GNOME**: ensure `gnome-shell-extension-appindicator` is installed
  and enabled. Log out and back in after enabling.
- **Xfce**: add "Indicator Plugin" to a panel.
- **Raspberry Pi OS (Wayland)**: install
  `gir1.2-ayatanaappindicator3-0.1` for tray support, or fall back to
  the GTK Layer Shell floating widget. The default `wf-panel-pi`
  hosts AppIndicator icons once the GIR is installed.
- Check the indicator is actually running:
  `pgrep -af indicator.py` (or
  `systemctl --user status ups-hat-b-indicator` on systemd installs).
- See which backend was selected:
  `python3 indicator.py --log-level INFO --mock`.

## "UPS: unavailable" in menu

- Run `./scripts/i2c-detect.sh` to verify the UPS HAT is at `0x42`.
- Check I2C is enabled: `ls /dev/i2c-*` should list at least
  `/dev/i2c-1`. If missing, `sudo raspi-config nonint do_i2c 0` then
  reboot.
- Verify permissions: your user should be in the `i2c` group:
  `id -nG | grep -w i2c`. If missing,
  `sudo usermod -aG i2c $USER` and re-login.

## Wrong voltage / percentage readings

- The default curve assumes a 2S Li-ion pack (6.0 V – 8.4 V).
  Customise `[battery.curve]` in `config.toml` if your pack differs —
  see [configuration.md](configuration.md).
- `python3 indicator.py --log-level DEBUG` shows raw readings every
  poll cycle.

## Notifications not appearing

- Ensure a notification daemon is running (e.g. `dunst`, `mako`, or
  the desktop's built-in one).
- Test manually: `notify-send "Test" "Hello"`.

## Service won't start

- Logs: `journalctl --user -u ups-hat-b-indicator -n 50`.
- Verify the service file path: `systemctl --user cat
  ups-hat-b-indicator`.
- Confirm the graphical session is active:
  `systemctl --user is-active graphical-session.target`.

## Pi OS Bookworm + wayvnc — service installs but never runs

Under `wayvnc` on Pi OS, the wayfire/labwc session does not signal
`graphical-session.target` to the user systemd manager, so a unit
with `WantedBy=graphical-session.target` is enabled but never
triggered. Use the XDG autostart path instead:

```bash
./install.sh --mode xdg
```

The desktop session reads `~/.config/autostart/*.desktop` directly
when the GUI starts, so the indicator launches with a working
Wayland/DBus environment regardless of whether
`graphical-session.target` fires.

## Shutdown not working when enabled

- Run `python3 indicator.py --test-shutdown` to diagnose.
- Most desktop sessions allow `poweroff` via polkit. If running
  headless, configure sudoers — see [shutdown.md](shutdown.md).

## Logging

Logs go to stderr; journald captures them when running as a service.

```bash
# Service logs
journalctl --user -u ups-hat-b-indicator -f

# Foreground with debug detail
python3 indicator.py --log-level DEBUG --mock
```

Levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.

When started by `install.sh` outside a service manager, stdout +
stderr land in `/tmp/ups-hat-b-indicator.log`.
