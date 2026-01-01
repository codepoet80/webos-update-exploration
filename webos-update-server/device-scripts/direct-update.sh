#!/bin/sh
# Direct Update Script for webOS WiFi-only devices
# Bypasses OmaDm carrier detection issue
#
# Usage: ./direct-update.sh [server_url]
# Example: ./direct-update.sh http://192.168.10.20:8080

SERVER_URL="${1:-http://192.168.10.20:8080}"
SESSION_DIR="/var/lib/software/SessionFiles"
UPDATE_DIR="/var/lib/update"
UPDATE_FLAG="/var/lib/software/updating"

# Get current build
get_current_build() {
    # Try to read from system
    if [ -f /etc/palm-build-info ]; then
        BUILD=$(grep "^BUILDNAME=" /etc/palm-build-info | cut -d= -f2)
        if [ -n "$BUILD" ]; then
            echo "$BUILD"
            return
        fi
    fi

    # Fallback to device info
    if [ -f /var/luna/preferences/deviceInfo.json ]; then
        BUILD=$(grep -o '"swVersion":"[^"]*"' /var/luna/preferences/deviceInfo.json | cut -d'"' -f4)
        if [ -n "$BUILD" ]; then
            echo "Nova-$BUILD"
            return
        fi
    fi

    # Default
    echo "Nova-3.0.5-86"
}

# Check for updates and get package list
check_updates() {
    BUILD=$(get_current_build)
    echo "Current build: $BUILD"
    echo "Checking server: $SERVER_URL"
    echo ""

    RESPONSE=$(curl -s "$SERVER_URL/api/updates/check?build=$BUILD")

    if echo "$RESPONSE" | grep -q '"updateAvailable":true'; then
        PACKAGE_COUNT=$(echo "$RESPONSE" | grep -o '"packageCount":[0-9]*' | cut -d: -f2)
        echo "Update available! ($PACKAGE_COUNT packages)"
        echo ""

        # Parse each package (simple extraction for busybox)
        # Store package info in temp files
        echo "$RESPONSE" > /tmp/update_response.json

        return 0
    else
        echo "No updates available"
        return 1
    fi
}

# Download all update packages
download_updates() {
    echo "Creating update directory..."
    mkdir -p "$UPDATE_DIR"

    # Clear old packages
    rm -f "$UPDATE_DIR"/*.ipk 2>/dev/null

    # Parse packages from response
    # This is a simple parser for the JSON format
    RESPONSE=$(cat /tmp/update_response.json)

    # Extract URLs using grep (busybox compatible)
    URLS=$(echo "$RESPONSE" | grep -o '"url":"[^"]*"' | cut -d'"' -f4)
    FILENAMES=$(echo "$RESPONSE" | grep -o '"filename":"[^"]*"' | cut -d'"' -f4)
    MD5S=$(echo "$RESPONSE" | grep -o '"md5":"[^"]*"' | cut -d'"' -f4)

    # Convert to arrays using temp files
    echo "$URLS" > /tmp/urls.txt
    echo "$FILENAMES" > /tmp/filenames.txt
    echo "$MD5S" > /tmp/md5s.txt

    DOWNLOAD_COUNT=0
    TOTAL=$(echo "$URLS" | wc -l)

    # Download each package
    while read -r URL && read -r FILENAME <&3 && read -r EXPECTED_MD5 <&4; do
        DOWNLOAD_COUNT=$((DOWNLOAD_COUNT + 1))
        echo "[$DOWNLOAD_COUNT/$TOTAL] Downloading: $FILENAME"

        curl -# -o "$UPDATE_DIR/$FILENAME" "$URL"

        if [ $? -eq 0 ] && [ -f "$UPDATE_DIR/$FILENAME" ]; then
            # Verify MD5
            ACTUAL_MD5=$(md5sum "$UPDATE_DIR/$FILENAME" 2>/dev/null | cut -d' ' -f1)
            if [ "$ACTUAL_MD5" = "$EXPECTED_MD5" ]; then
                echo "    MD5 verified"
            else
                echo "    WARNING: MD5 mismatch!"
                echo "    Expected: $EXPECTED_MD5"
                echo "    Actual:   $ACTUAL_MD5"
            fi
        else
            echo "    Download failed!"
            return 1
        fi
    done < /tmp/urls.txt 3< /tmp/filenames.txt 4< /tmp/md5s.txt

    echo ""
    echo "Downloaded $DOWNLOAD_COUNT packages"
    return 0
}

# Create session files for UpdateDaemon
create_session_files() {
    echo "Creating session files..."
    mkdir -p "$SESSION_DIR"

    # Clear old session files
    rm -f "$SESSION_DIR/urls" 2>/dev/null
    rm -f "$SESSION_DIR/update_list.txt" 2>/dev/null
    rm -f "$SESSION_DIR/install_list.txt" 2>/dev/null
    rm -f "$SESSION_DIR/update_status.txt" 2>/dev/null
    rm -f "$SESSION_DIR/download_status.txt" 2>/dev/null

    # Create URLs file (all download URLs)
    cat /tmp/urls.txt > "$SESSION_DIR/urls"
    echo "Created: $SESSION_DIR/urls"

    # Create update list (paths to downloaded packages)
    # updatefsinfo must be first!
    for FILENAME in $(cat /tmp/filenames.txt); do
        echo "$UPDATE_DIR/$FILENAME"
    done | sort -r > "$SESSION_DIR/update_list.txt"
    echo "Created: $SESSION_DIR/update_list.txt"

    # Create install list (same paths but with /rootfs prefix for PmUpdater)
    # This is CRITICAL - PmUpdater runs in OTA ramdisk where rootfs is at /rootfs
    for FILENAME in $(cat /tmp/filenames.txt); do
        echo "/rootfs$UPDATE_DIR/$FILENAME"
    done | sort -r > "$SESSION_DIR/install_list.txt"
    echo "Created: $SESSION_DIR/install_list.txt"

    # Show contents
    echo ""
    echo "Package list:"
    cat "$SESSION_DIR/update_list.txt" | while read line; do
        echo "  - $line"
    done

    # Create update flag
    echo "1" > "$UPDATE_FLAG"
    echo ""
    echo "Created: $UPDATE_FLAG"

    return 0
}

# Show installation instructions
show_install_instructions() {
    echo ""
    echo "========================================"
    echo "       UPDATE READY TO INSTALL"
    echo "========================================"
    echo ""
    echo "Packages downloaded and session files created."
    echo ""
    echo "To install the update:"
    echo "1. The device will reboot into update mode"
    echo "2. Packages will be installed"
    echo "3. Device will reboot again when done"
    echo ""
    echo "Run this command to start installation:"
    echo ""
    echo "  /usr/share/ota-scripts/make-update-uimage && reboot"
    echo ""
    echo "Or to test make-update-uimage first:"
    echo "  /usr/share/ota-scripts/make-update-uimage"
    echo "  cat /var/log/uimage.log"
    echo ""
    echo "========================================"
}

# Clean up temp files
cleanup() {
    rm -f /tmp/update_response.json
    rm -f /tmp/urls.txt
    rm -f /tmp/filenames.txt
    rm -f /tmp/md5s.txt
}

# Main
main() {
    echo "========================================"
    echo "    webOS Direct Update Tool"
    echo "========================================"
    echo ""

    if ! check_updates; then
        cleanup
        exit 0
    fi

    echo ""
    read -p "Download and prepare update? [y/N] " REPLY
    case "$REPLY" in
        [yY]|[yY][eE][sS])
            ;;
        *)
            echo "Cancelled."
            cleanup
            exit 0
            ;;
    esac

    echo ""
    if ! download_updates; then
        echo "Download failed!"
        cleanup
        exit 1
    fi

    if ! create_session_files; then
        echo "Failed to create session files!"
        cleanup
        exit 1
    fi

    show_install_instructions
    cleanup
}

# Run with -y for non-interactive mode
if [ "$2" = "-y" ]; then
    if ! check_updates; then
        cleanup
        exit 0
    fi
    if ! download_updates; then
        cleanup
        exit 1
    fi
    if ! create_session_files; then
        cleanup
        exit 1
    fi
    show_install_instructions
    cleanup
else
    main
fi
