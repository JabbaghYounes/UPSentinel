# Configuration

Configuration file: `~/.config/ups-hat-b/config.toml`

All fields are optional; defaults apply when omitted.

```toml
[i2c]
bus = 1
addr = "0x42"

[indicator]
interval = 5       # poll interval in seconds
backend = "auto"   # auto, appindicator, layershell, notification

[battery]
warn_percent = 20
critical_percent = 10

# Custom voltage-to-percent curve: [[voltage, percent], ...]
curve = [
    [6.0, 0],
    [6.4, 5],
    [6.8, 10],
    [7.0, 20],
    [7.2, 40],
    [7.4, 60],
    [7.6, 80],
    [7.9, 90],
    [8.2, 95],
    [8.4, 100],
]

[shutdown]
enabled = false     # opt-in: set true to enable auto-shutdown
percent = 5         # shutdown when battery drops to this level

# Only used when backend = "layershell". Pixel-positioned floating
# widget — defaults are tuned for Pi OS Bookworm wf-panel-pi (sits in
# the panel strip at top-right, just left of the clock).
[layershell]
anchor_top = true
anchor_right = true
anchor_bottom = false
anchor_left = false
margin_top = 2
margin_right = 110
margin_bottom = 0
margin_left = 0
```

## Priority

Highest to lowest:

1. CLI flags
2. Environment variables (`UPS_I2C_BUS`, `UPS_I2C_ADDR`)
3. Config file
4. Built-in defaults

## Voltage curve

The default curve assumes a 2S Li-ion pack (6.0 V – 8.4 V), which is
what the Waveshare UPS HAT (B) ships with. Override `[battery.curve]`
if your pack differs.

## Backend pinning

`./install.sh` pins `backend = "appindicator"` so multiple
deployments render identically and a missing GIR doesn't silently fall
back to LayerShell or notification-only. Set `backend = "auto"` to
restore detection-based selection.

On Pi OS Bookworm under wayfire/labwc, `wf-panel-pi`'s `tray` widget
is an XEmbed tray, not a StatusNotifierItem host — it can't display
AppIndicator items. Switch to LayerShell:

```toml
[indicator]
backend = "layershell"
```

## LayerShell placement

The LayerShell widget is anchored to screen edges via
`anchor_top|bottom|left|right` (booleans) and offset with
`margin_*` (pixels). Defaults place the widget inside the Pi OS
panel strip at top-right, just left of the clock. Common tweaks:

- **Move further from the clock**: increase `margin_right`.
- **Drop below the panel**: set `margin_top = 32` (panel is ~28 px).
- **Bottom-left corner**: `anchor_top = false`, `anchor_bottom = true`,
  `anchor_right = false`, `anchor_left = true`, then set the
  corresponding margins.

## Related docs

- [Safe shutdown setup](shutdown.md)
- [CLI usage](usage.md)
