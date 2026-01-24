#!/usr/bin/env bash
# I2C detection helper for UPS HAT (B)
# Checks for i2cdetect, scans bus 1, and reports UPS HAT presence.

set -euo pipefail

BUS="${UPS_I2C_BUS:-1}"
EXPECTED_ADDR="42"

echo "=== UPS HAT (B) I2C Diagnostics ==="
echo

# Check if i2cdetect is available
if ! command -v i2cdetect &>/dev/null; then
    echo "ERROR: i2cdetect not found."
    echo "Install it with:  sudo apt install i2c-tools"
    exit 1
fi

echo "Found i2cdetect: $(command -v i2cdetect)"
echo "Scanning I2C bus ${BUS}..."
echo

OUTPUT=$(i2cdetect -y "$BUS" 2>&1) || {
    echo "ERROR: Failed to run i2cdetect on bus ${BUS}."
    echo "Possible causes:"
    echo "  - I2C not enabled (check raspi-config or /boot/config.txt)"
    echo "  - Insufficient permissions (try running with sudo)"
    echo "  - Bus ${BUS} does not exist"
    exit 1
}

echo "$OUTPUT"
echo

# Check for the expected address
if echo "$OUTPUT" | grep -qw "$EXPECTED_ADDR"; then
    echo "OK: Device found at 0x${EXPECTED_ADDR} on bus ${BUS}."
    echo "UPS HAT (B) appears to be connected."
else
    echo "WARNING: Device NOT found at 0x${EXPECTED_ADDR} on bus ${BUS}."
    echo
    echo "Hints:"
    echo "  - Check that the UPS HAT (B) is properly seated on the GPIO header"
    echo "  - Verify I2C is enabled: sudo raspi-config -> Interface Options -> I2C"
    echo "  - Check /boot/config.txt contains: dtparam=i2c_arm=on"
    echo "  - Try a different bus with: UPS_I2C_BUS=0 $0"
    exit 1
fi
