#!/bin/bash
#
# Deploy DmTree.xml to HP TouchPad
#
# This script copies the modified DmTree.xml to redirect the device
# to your local update server instead of the defunct Palm servers.
#
# Prerequisites:
# - Developer mode enabled on TouchPad
# - USB connection established
# - novacom or SSH access available
#
# Usage:
#   ./deploy.sh <server_ip>
#
# Example:
#   ./deploy.sh 192.168.1.100
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DMTREE_SOURCE="${SCRIPT_DIR}/DmTree.xml"
DMTREE_DEST="/usr/share/omadm/DmTree.xml"
SERVER_PORT="8080"

if [ -z "$1" ]; then
    echo "Usage: $0 <server_ip>"
    echo ""
    echo "Example: $0 192.168.1.100"
    echo ""
    echo "This will configure the TouchPad to use:"
    echo "  http://<server_ip>:${SERVER_PORT}/palmcsext/swupdateserver"
    exit 1
fi

SERVER_IP="$1"
SERVER_URL="http://${SERVER_IP}:${SERVER_PORT}/palmcsext/swupdateserver"

echo "================================================"
echo "webOS Update Server - Device Deployment"
echo "================================================"
echo ""
echo "Server IP: ${SERVER_IP}"
echo "Server URL: ${SERVER_URL}"
echo ""

# Create temporary modified DmTree.xml
TEMP_DMTREE=$(mktemp)
sed "s|YOUR_SERVER_IP|${SERVER_IP}|g" "${DMTREE_SOURCE}" > "${TEMP_DMTREE}"

echo "Modified DmTree.xml created with server URL: ${SERVER_URL}"
echo ""

# Check for novacom
if command -v novacom &> /dev/null; then
    echo "Using novacom for deployment..."
    echo ""

    # Check device connection
    if ! novacom -l 2>/dev/null | grep -q "device"; then
        echo "ERROR: No device found. Please connect your TouchPad via USB."
        rm "${TEMP_DMTREE}"
        exit 1
    fi

    echo "Device found. Deploying..."

    # Remount root filesystem as read-write
    echo "Remounting filesystem as read-write..."
    novacom run -- "mount -o remount,rw /"

    # Backup original DmTree.xml
    echo "Backing up original DmTree.xml..."
    novacom run -- "cp ${DMTREE_DEST} ${DMTREE_DEST}.backup" 2>/dev/null || true

    # Copy modified DmTree.xml
    echo "Copying modified DmTree.xml..."
    novacom put "file://${DMTREE_DEST}" < "${TEMP_DMTREE}"

    # Remount as read-only
    echo "Remounting filesystem as read-only..."
    novacom run -- "mount -o remount,ro /"

    echo ""
    echo "Deployment complete!"

elif command -v ssh &> /dev/null; then
    echo "novacom not found. Attempting SSH deployment..."
    echo ""
    echo "Enter the TouchPad IP address (or press Enter for USB networking 172.16.42.1):"
    read -r TOUCHPAD_IP
    TOUCHPAD_IP="${TOUCHPAD_IP:-172.16.42.1}"

    echo "Connecting to ${TOUCHPAD_IP}..."

    # Copy via SCP and apply
    echo "Copying DmTree.xml..."
    scp "${TEMP_DMTREE}" "root@${TOUCHPAD_IP}:/tmp/DmTree.xml"

    echo "Applying configuration..."
    ssh "root@${TOUCHPAD_IP}" << 'REMOTE_SCRIPT'
        mount -o remount,rw /
        cp /usr/share/omadm/DmTree.xml /usr/share/omadm/DmTree.xml.backup 2>/dev/null || true
        cp /tmp/DmTree.xml /usr/share/omadm/DmTree.xml
        mount -o remount,ro /
        rm /tmp/DmTree.xml
REMOTE_SCRIPT

    echo ""
    echo "Deployment complete!"

else
    echo "Neither novacom nor ssh found."
    echo ""
    echo "Manual deployment instructions:"
    echo "================================"
    echo ""
    echo "1. Enable developer mode on TouchPad"
    echo "2. Connect via USB or SSH"
    echo "3. Run: mount -o remount,rw /"
    echo "4. Backup: cp ${DMTREE_DEST} ${DMTREE_DEST}.backup"
    echo "5. Copy the modified DmTree.xml to ${DMTREE_DEST}"
    echo "6. Run: mount -o remount,ro /"
    echo ""
    echo "The modified DmTree.xml has been saved to: ${TEMP_DMTREE}"
    echo ""
    echo "Make sure to update YOUR_SERVER_IP in the file to your actual server IP."
    exit 0
fi

rm "${TEMP_DMTREE}"

echo ""
echo "================================================"
echo "Next steps:"
echo "================================================"
echo ""
echo "1. Start the update server on your computer:"
echo "   cd webos-update-server"
echo "   python server.py"
echo ""
echo "2. On the TouchPad, open the Updates app"
echo "   or trigger an update check manually"
echo ""
echo "3. The device should now connect to your local server"
echo ""
echo "To restore original configuration:"
echo "   novacom run -- 'mount -o remount,rw /'"
echo "   novacom run -- 'cp ${DMTREE_DEST}.backup ${DMTREE_DEST}'"
echo "   novacom run -- 'mount -o remount,ro /'"
echo ""
