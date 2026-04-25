# Safe shutdown (opt-in)

Shutdown is **disabled by default**. When enabled, the indicator
calls `systemctl poweroff` exactly once when the battery drops to
`shutdown.percent`. Re-arming requires an indicator restart.

## Enable

1. Add to `~/.config/ups-hat-b/config.toml`:

   ```toml
   [shutdown]
   enabled = true
   percent = 5
   ```

2. Ensure the user has permission to shut down. Two options:

   **Option A — Polkit (default on most desktops):** most desktop
   sessions already allow the logged-in user to `poweroff` via
   polkit, no config needed.

   **Option B — Sudoers (headless / service setups):**

   ```bash
   echo "youruser ALL=(ALL) NOPASSWD: /usr/bin/systemctl poweroff" | \
       sudo tee /etc/sudoers.d/ups-shutdown
   ```

3. Verify with the dry-run flag (no actual shutdown):

   ```bash
   python3 indicator.py --test-shutdown \
       --config ~/.config/ups-hat-b/config.toml
   ```

   Expected: a "would shut down now" log line and a notification, no
   poweroff.

## How it triggers

- Fires the moment `percent <= shutdown.percent`.
- Guarded by `_shutdown_triggered` so it only fires once per
  indicator process — important so a reading bouncing across the
  threshold doesn't repeatedly issue `systemctl poweroff`.
- A "Shutdown imminent" notification is sent immediately before the
  call.
