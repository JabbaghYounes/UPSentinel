# UPSentinel — Deployment session report and follow-up task

**Date:** 2026-04-25
**Context:** Deployed UPSentinel onto both AutonoBird Benchy test Pis as part of the dissertation bench setup. UPSentinel runs alongside Benchy on these two Pis to provide visible UPS battery monitoring while the NPU benchmark runs.

## Hosts deployed onto

| Label | Host / IP | User | Hardware |
|---|---|---|---|
| Pi A | `snpi@192.168.0.15` | `snpi` | Pi 5 / 16 GB / AI HAT+ (Hailo-8) / Waveshare UPS HAT (B) |
| Pi B | `vpn@192.168.0.130` | `vpn` | Pi 5 / 4 GB / AI HAT+ 2 (Hailo-10H) / Waveshare UPS HAT (B) |

Both run Pi OS Bookworm (aarch64), Wayland session served via `wayvnc` for headless access. Neither is the AutonoBird drone Pi — those test rigs are bench-only for the Benchy NPU benchmark. The drone itself is UBEC-powered and does not run UPSentinel.

UPSentinel installed at `~/Documents/UPSentinel/` on both Pis.

## Actions taken (chronological)

### 1. Hardware verification

On each Pi, ran `sudo i2cdetect -y 1` to confirm the Waveshare UPS HAT (B)'s INA219 chip is reachable. Both showed the chip at address `0x42`. Also ran the Waveshare-supplied `INA219.py` script directly to confirm sane readings (voltage, current, power, percent) before installing UPSentinel.

### 2. System dependency installation (both Pis)

```bash
sudo apt update
sudo apt install -y \
    python3-gi \
    gir1.2-ayatanaappindicator3-0.1 \
    libgtk-layer-shell0 \
    gir1.2-gtklayershell-0.1 \
    python3-smbus2 \
    i2c-tools \
    libnotify-bin
```

Note: on Pi B, `gir1.2-gtklayershell-0.1` and `gir1.2-ayatanaappindicator3-0.1` did not register from the first run of this command (verified via `dpkg -l`). Both had to be installed explicitly in a follow-up step. Cause not root-caused — possibly a stale `apt` cache or a transient mirror error. Recommendation for the install README: after the apt block, run a `dpkg -l | grep` verify step.

### 3. Repository clone (both Pis)

```bash
cd ~
git clone https://github.com/JabbaghYounes/UPSentinel.git
```

(Note: Pi B ended up with the repo at `~/Documents/UPSentinel` rather than `~/UPSentinel`. Either path works; the `.desktop` autostart file references the actual install path.)

### 4. Initial smoke test from SSH (failed predictably)

Running `python3 indicator.py --log-level INFO` over SSH dropped into `notification-only` backend on Pi B and `appindicator` on Pi A — but neither had a working tray icon. Diagnosis:

- `XDG_SESSION_TYPE` was `tty` (not `wayland`) in the SSH session — the SSH login is a TTY session, not a graphical one, so GTK clients have no Wayland display to render to.
- `loginctl list-sessions` showed sessions but no graphical session was actually active for the user.

This is expected behavior: UPSentinel is a desktop tray indicator and must be launched from inside the desktop session (or via a session-aware autostart mechanism), not from an SSH terminal.

### 5. systemd user service install (failed on Pi OS Bookworm wayvnc)

Ran `./scripts/install-user-service.sh` on both Pis. Service installed successfully but did not start the indicator after reboot/login. Diagnosis via `systemctl --user is-active graphical-session.target` returned `inactive` on both Pis even with an active VNC desktop session.

**Root cause:** Pi OS Bookworm's session manager (wayfire / labwc with `wf-panel-pi`), when started under `wayvnc`, does not signal `graphical-session.target` to the user systemd manager. Services with `WantedBy=graphical-session.target` therefore never trigger. Pi A's logs confirmed the service did briefly run once but exited with `Error reading events from display: Broken pipe` — the GTK display connection was severed because the service started outside the graphical session.

This is a known interaction between `wayvnc` and `systemd --user`. The systemd user service approach in `scripts/install-user-service.sh` is the textbook recommendation but does not work reliably on Pi OS Bookworm under VNC.

### 6. Switched to XDG autostart (worked)

Disabled the systemd user service:

```bash
systemctl --user disable --now ups-hat-b-indicator
rm -f ~/.config/systemd/user/graphical-session.target.wants/ups-hat-b-indicator.service
```

Created an XDG autostart entry that the desktop session manager (wayfire / labwc) picks up directly when the GUI session starts:

```bash
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/ups-hat-b-indicator.desktop << EOF
[Desktop Entry]
Type=Application
Name=UPS HAT (B) Indicator
Comment=Tray indicator for Waveshare UPS HAT (B)
Exec=/usr/bin/python3 $HOME/Documents/UPSentinel/indicator.py
X-GNOME-Autostart-enabled=true
NoDisplay=false
EOF
```

After reboot + VNC login, the indicator launches as part of the desktop session with the correct Wayland/DBUS environment.

**Recommendation for upstream:** Document the `wayvnc` issue in the README and provide an XDG-autostart-based install script as the recommended path for Pi OS Bookworm. Keep the systemd user service script for distros where `graphical-session.target` is reliably activated (most desktop Linux). A flag on `install-user-service.sh` to choose between the two install modes would be ideal.

### 7. Backend visual inconsistency between the two Pis

Pi A picked `appindicator` (system tray icon integrated into `wf-panel-pi`'s tray slot — looks "native", same row as bluetooth/wifi/clock).

Pi B picked `layershell` (a floating GTK widget overlaid on top of the panel — visually distinct from the panel's tray icons).

**Cause:** UPSentinel's auto-detection in `ups/backends/__init__.py` (`detect_backend`) tries `appindicator` first via the GIR availability check. On Pi B, `gir1.2-ayatanaappindicator3-0.1` was not actually installed (despite being in the original apt block — see step 2). Auto-detect therefore fell back to `layershell` on Pi B but selected `appindicator` on Pi A.

### 8. Forced backend consistency

Installed the missing GIR on Pi B:

```bash
sudo apt install -y gir1.2-ayatanaappindicator3-0.1
```

Locked both Pis to AppIndicator deterministically via config:

```bash
mkdir -p ~/.config/ups-hat-b
cat > ~/.config/ups-hat-b/config.toml << 'EOF'
[indicator]
backend = "appindicator"
EOF
```

Both Pis now show the same battery icon in the same place (`wf-panel-pi` tray, top-right, alongside bluetooth/wifi/clock). End-state confirmed visually via VNC on both hosts.

## Final deployment state

- **Backend:** `appindicator` (forced via `~/.config/ups-hat-b/config.toml`) on both Pis.
- **Autostart:** XDG `.desktop` file in `~/.config/autostart/`. Survives reboot.
- **Display:** Battery icon in `wf-panel-pi` tray. Click → menu with voltage / current / power / percent / discharge state and a Quit option.
- **Configuration file:** `~/.config/ups-hat-b/config.toml` — currently only sets the backend. Default voltage curve (2S Li-ion 6.0 V – 8.4 V) is appropriate for the Waveshare UPS HAT (B)'s included pack.

## Open question raised during deployment

**Why did Pi A's `wf-panel-pi` host AppIndicator icons but Pi B's also did once we installed the GIR?** Both are stock Pi OS Bookworm with the same desktop. After the Pi B fix, both behave identically, so the apparent earlier asymmetry was purely a missing-package issue. No panel config divergence — `wf-panel-pi` has tray-host capability out of the box on Pi OS Bookworm and renders both `org.kde.StatusNotifierItem` and `org.ayatana.indicator.appindicator` services correctly.

---

## Follow-up task (Task 2) — Custom blue battery icons

**Status:** Deferred for a follow-up Claude Code session. Out of scope for the dissertation timeline (deadline 2026-04-30); this is polish, not a blocker.

### Goal

Replace the freedesktop standard icons (`battery-good-symbolic`, `battery-low-symbolic`, etc.) currently used by `ICON_MAP` in `ups/backends/__init__.py` with a custom UPSentinel-bundled icon set. Visual style:

- **White outline** for the battery shape (stroke, no fill).
- **Blue interior fill** representing the percentage (proportional rectangle inside the outline, suggested colour `#1e9bff` or another Pi-OS-palette-matching blue).
- **Lightning-bolt overlay** for the charging variants.
- **Red caution** for the < 10 % critical variant.

This keeps the look consistent across icon themes, between the two Pis, and any future deployment, by burning the design into the project rather than relying on whatever theme is active.

### Suggested implementation

1. **Add SVGs to `icons/`** (currently empty except for `.gitkeep`):
   - `battery-100.svg` `battery-90.svg` `battery-80.svg` `battery-70.svg` `battery-60.svg` `battery-50.svg` `battery-40.svg` `battery-30.svg` `battery-20.svg` `battery-10.svg` `battery-0.svg`
   - Charging variants: `battery-100-charging.svg` … `battery-0-charging.svg`
   - Or fewer buckets matching the existing `ICON_MAP` ranges (caution / low / good / full).
   - Symbolic-icon size: 24×24 viewBox is the GTK convention.

2. **Modify `ICON_MAP` in `ups/backends/__init__.py`** to return absolute paths resolved relative to the project root rather than freedesktop names. Suggested pattern:

   ```python
   from pathlib import Path
   ICONS_DIR = Path(__file__).resolve().parent.parent.parent / "icons"

   def get_icon_name(status: UPSStatus | None) -> str:
       ...
       return str(ICONS_DIR / f"battery-{bucket}.svg")
   ```

3. **Verify on both backends.** AppIndicator's `set_icon_full` and the LayerShell GTK widget both accept absolute file paths in addition to theme icon names. Notification urgency icons also accept absolute paths via `Notify.Notification.new(summary, body, icon_path)`.

4. **Tests.** Add a unit test in `tests/` that asserts every icon path returned by `get_icon_name` exists on disk. This catches typos and missing variants at CI time.

5. **README update.** Document the icon source-of-truth and how to regenerate / edit them. Link to the dissertation reference.

### Acceptance criteria

- Same battery icon style on Pi A and Pi B regardless of GTK icon theme.
- Charging vs discharging visually distinguishable.
- Critical (< 10 %) state visibly different (red highlight or full red icon).
- No regression to mock mode or `--backend notification` fallback.

### Out of scope for Task 2

- Animation (battery fill animating up while charging) — nice-to-have, not asked for.
- Theme switcher (multiple colour palettes) — single blue theme is enough.
- Replacing the menu/widget chrome — only the battery glyph itself.

---

## Cross-reference

This deployment was part of the AutonoBird dissertation Stage 2 wrap-up on 2026-04-25 (early hours). UPSentinel will be referenced in the dissertation under supporting tooling. The two Pis it runs on are also the Benchy test rigs that select between the AI HAT+ (Hailo-8) and AI HAT+ 2 (Hailo-10H) for the AutonoBird perception stack. The drone itself does **not** run UPSentinel — it is UBEC-powered, not UPS-HAT-powered, since the Waveshare UPS HAT was dropped early in the AutonoBird build due to vibration-induced pogo-pin failures.

## Related articles must check out

1. https://fruitbox4dummies.com/pi4-pi5/

2. https://www.raspberrypi.com/news/bookworm-the-new-version-of-raspberry-pi-os/

3. https://github.com/meowmeowahr/papirus-icon-theme-rpi#hardcoded-icons

## Considerations

Yes — if auto-login is enabled (Pi OS default).

  The mechanism: XDG autostart fires when the desktop session starts, not on system boot directly. So the chain is:

  1. Pi boots
  2. Display manager (lightdm) reaches login
  3. If auto-login is on → desktop session starts immediately without user input
  4. wayfire / labwc / wf-panel-pi reads ~/.config/autostart/*.desktop and launches each entry
  5. UPSentinel starts

  If you set the Pi to require manual login (raspi-config → "Boot to Desktop, requires Login"), then UPSentinel only starts after someone logs into the desktop via VNC. SSH-only access does
  not trigger the autostart — SSH is a TTY session, not a graphical one.

  Quick verify on Pi B without rebooting:

  # Is auto-login on? (B = Boot, default Pi OS choice = "B4" auto-login to desktop)
  sudo raspi-config nonint get_autologin
  # 0 = auto-login enabled, 1 = disabled

  Or to test end-to-end: reboot Pi B, then immediately SSH in (do NOT open VNC) and run:

  sleep 30
  pgrep -af indicator.py

  If indicator.py is running, autostart fires on boot via auto-login → UPSentinel is "startup launch" in the practical sense. If not running, you'd need to VNC in once for it to start.

