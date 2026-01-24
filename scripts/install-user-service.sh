#!/usr/bin/env bash
# Install the UPS HAT (B) indicator as a systemd user service.
#
# Usage:
#   ./scripts/install-user-service.sh
#
# This script:
#   1. Determines the project directory
#   2. Generates the systemd service file with the correct path
#   3. Installs it to ~/.config/systemd/user/
#   4. Reloads the systemd user daemon
#   5. Enables and starts the service

set -euo pipefail

SERVICE_NAME="ups-hat-b-indicator"
SERVICE_FILE="${SERVICE_NAME}.service"
USER_SYSTEMD_DIR="${HOME}/.config/systemd/user"

# Resolve the project root (parent of scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== UPS HAT (B) Indicator - Service Installer ==="
echo
echo "Project directory: ${PROJECT_DIR}"
echo "Service will be installed to: ${USER_SYSTEMD_DIR}/${SERVICE_FILE}"
echo

# Verify indicator.py exists
if [[ ! -f "${PROJECT_DIR}/indicator.py" ]]; then
    echo "ERROR: indicator.py not found in ${PROJECT_DIR}"
    exit 1
fi

# Create systemd user directory if needed
mkdir -p "${USER_SYSTEMD_DIR}"

# Generate service file with actual install path
sed "s|__INSTALL_DIR__|${PROJECT_DIR}|g" \
    "${PROJECT_DIR}/systemd/${SERVICE_FILE}" \
    > "${USER_SYSTEMD_DIR}/${SERVICE_FILE}"

echo "Installed service file."

# Reload systemd user daemon
systemctl --user daemon-reload
echo "Reloaded systemd user daemon."

# Enable and start
systemctl --user enable --now "${SERVICE_NAME}"
echo
echo "Service enabled and started."
echo
echo "Useful commands:"
echo "  Status:   systemctl --user status ${SERVICE_NAME}"
echo "  Logs:     journalctl --user -u ${SERVICE_NAME} -f"
echo "  Stop:     systemctl --user stop ${SERVICE_NAME}"
echo "  Disable:  systemctl --user disable --now ${SERVICE_NAME}"
