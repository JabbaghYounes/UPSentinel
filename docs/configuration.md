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

## Related docs

- [Safe shutdown setup](shutdown.md)
- [CLI usage](usage.md)
