# HP TouchPad OTA Update Guide

This guide explains how to create, stage, and deploy OTA (Over-The-Air) updates to an HP TouchPad running webOS 3.0.5.

## Prerequisites

### Hardware
- HP TouchPad with webOS 3.0.5 installed
- USB cable for novacom connection
- Computer running macOS, Linux, or Windows

### Software
- **novacom** - Palm/HP's USB communication tool
  - macOS: Install from Palm SDK or use Homebrew
  - Linux: Available in Palm SDK
  - Windows: Install Palm SDK or standalone novacom driver
- **Python 3.8+** (for the update server)
- **ar, tar, gzip** (standard Unix tools for building packages)

### Verify Connection

```bash
# Check that your TouchPad is connected and recognized
novacom -l

# Expected output:
# 12345 abc123... usb topaz-linux
```

If no device appears:
1. Enable Developer Mode on the TouchPad (Settings > Device Info > tap webOS version 5 times)
2. Reconnect USB cable
3. On macOS/Linux, ensure novacomd is running: `novacomd &`

---

## Part 1: Creating Update Packages

### Package Structure

Each package needs:
```
my-package/
├── CONTROL/
│   ├── control      # Package metadata (required)
│   └── postinst     # Post-install script (optional)
└── data/
    └── ...          # Files to install (mirrors device filesystem)
```

### Step 1.1: Create the Control File

Create `CONTROL/control` with these **required** fields:

```
Package: com.example.mypackage
Version: 1.0.0
Section: misc
Priority: optional
Architecture: all
Installed-Size: 1
Maintainer: Your Name <you@example.com>
Description: Brief description of your package.
webOS-Package-Format-Version: 2
webOS-Packager-Version: 3.0.5b38
```

**Important Notes:**
- `webOS-Package-Format-Version: 2` and `webOS-Packager-Version: 3.0.5b38` are **required** - without them, ipkg will reject the package
- Use `com.palm.*` prefix for packages that need system privileges
- `Installed-Size` can be approximate (in KB)

### Step 1.2: Create Post-Install Script (Optional)

Create `CONTROL/postinst` if you need to run commands after installation:

```bash
#!/bin/sh
# Post-install script

echo "Package installed successfully!"

# Example: Create a marker file
echo "Installed on $(date)" > /media/internal/my-package-installed.txt

exit 0
```

Make it executable: `chmod +x CONTROL/postinst`

### Step 1.3: Add Data Files

Place files in `data/` mirroring the device filesystem:

```
data/
├── media/
│   └── internal/
│       └── myfile.txt          # Installs to /media/internal/myfile.txt
└── usr/
    └── palm/
        └── applications/
            └── com.example.app/
                └── ...          # Installs to /usr/palm/applications/...
```

### Step 1.4: Build the IPK

```bash
#!/bin/bash
# build-package.sh

PACKAGE_DIR="my-package"
WORK_DIR="/tmp/ipk-build"
OUTPUT="my-package_1.0.0_all.ipk"

# Clean and create work directory
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"

# Create debian-binary
echo "2.0" > "$WORK_DIR/debian-binary"

# Create control.tar.gz (MUST have ./ prefix and root ownership)
cd "$PACKAGE_DIR/CONTROL"
tar --uid=0 --gid=0 -czf "$WORK_DIR/control.tar.gz" ./control ./postinst 2>/dev/null || \
tar --uid=0 --gid=0 -czf "$WORK_DIR/control.tar.gz" ./control

# Create data.tar.gz (MUST have ./ prefix and root ownership)
cd "$PACKAGE_DIR/data"
tar --uid=0 --gid=0 -czf "$WORK_DIR/data.tar.gz" ./*

# Create IPK (order matters!)
cd "$WORK_DIR"
ar -cr "$OUTPUT" debian-binary control.tar.gz data.tar.gz

echo "Created: $OUTPUT"
echo "Size: $(stat -f%z "$OUTPUT" 2>/dev/null || stat -c%s "$OUTPUT") bytes"
echo "MD5: $(md5sum "$OUTPUT" | cut -d' ' -f1)"
```

### Step 1.5: Create updatefsinfo Package

**Every OTA update requires an `updatefsinfo` package** that tells the system about the update. Create this structure:

```
updatefsinfo/
├── CONTROL/
│   └── control
└── boot/
    └── updatefs-info
```

`CONTROL/control`:
```
Package: updatefsinfo
Version: 1.0.0
Section: misc
Priority: optional
Architecture: all
Installed-Size: 1
Maintainer: Your Name <you@example.com>
Description: Update filesystem info for OTA update.
webOS-Package-Format-Version: 2
webOS-Packager-Version: 3.0.5b38
```

`boot/updatefs-info`:
```
UPDATEFS_VERSION=1.0.0
UPDATEFS_KB=15000
UPDATEFS_INODES=640
```

---

## Part 2: Staging the Update

### Step 2.1: Upload Packages to Device

```bash
# Upload updatefsinfo (required for OTA)
novacom put file:///var/lib/update/updatefsinfo_1.0.0_all.ipk < updatefsinfo_1.0.0_all.ipk

# Upload your package(s)
novacom put file:///var/lib/update/com.example.mypackage_1.0.0_all.ipk < com.example.mypackage_1.0.0_all.ipk
```

Verify uploads:
```bash
novacom run "file://bin/ls -la /var/lib/update/"
```

### Step 2.2: Create Session Files

The OTA system requires specific session files. **Filenames must exactly match the uploaded packages!**

```bash
# Create update_list.txt (used by make-update-uimage)
echo '/var/lib/update/updatefsinfo_1.0.0_all.ipk
/var/lib/update/com.example.mypackage_1.0.0_all.ipk' | novacom put file:///var/lib/software/SessionFiles/update_list.txt

# Create install_list.txt (used by PmUpdater in OTA ramdisk)
# Note: Paths have /rootfs prefix because ramdisk mounts rootfs there
echo '/rootfs/var/lib/update/updatefsinfo_1.0.0_all.ipk
/rootfs/var/lib/update/com.example.mypackage_1.0.0_all.ipk' | novacom put file:///var/lib/software/SessionFiles/install_list.txt

# Set the updating flag
echo '1' | novacom put file:///var/lib/software/updating
```

Verify session files:
```bash
novacom run "file://bin/cat /var/lib/software/SessionFiles/update_list.txt"
novacom run "file://bin/cat /var/lib/software/SessionFiles/install_list.txt"
novacom run "file://bin/cat /var/lib/software/updating"
```

### Step 2.3: Clear Old Status (Optional)

```bash
novacom run "file://bin/rm /var/lib/software/SessionFiles/update_status.txt" 2>/dev/null
```

---

## Part 3: Deploying the Update

### Step 3.1: Create Update Image

This builds a ~9MB ramdisk that the device boots into for the update:

```bash
novacom run "file:///usr/share/ota-scripts/make-update-uimage"
```

This takes 30-60 seconds. When complete, verify:
```bash
novacom run "file://bin/ls -la /boot/uImage /boot/update-uimage"
```

You should see:
- `/boot/update-uimage` - The new update ramdisk (~9MB)
- `/boot/uImage` - Symlink pointing to `update-uimage`

### Step 3.2: Reboot into Update Mode

```bash
novacom run "file://sbin/reboot"
```

**What happens next:**
1. Device reboots into the update ramdisk
2. Pre-update script saves user data
3. PmUpdater installs your packages
4. Post-update script runs cleanup
5. Device reboots back to normal

### Step 3.3: Monitor Progress (Optional)

If you reconnect via novacom while in update mode:

```bash
# Check if still in OTA ramdisk (look for /rootfs mount)
novacom run "file://bin/mount" | grep rootfs

# Check progress (0=start, 1=pre-update done, 2=install done)
novacom run "file://bin/cat /rootfs/var/log/progress"

# Check installation status
novacom run "file://bin/cat /rootfs/var/lib/software/SessionFiles/update_status.txt"
```

---

## Part 4: Verifying the Update

After the device reboots normally:

### Check Package Status

```bash
# Verify package is installed
novacom run "file://usr/bin/ipkg status com.example.mypackage"

# Or using mmipkg
novacom run "file://usr/bin/mmipkg status com.example.mypackage"
```

### Check Your Files

```bash
# Example: Check if your files were installed
novacom run "file://bin/cat /media/internal/my-package-installed.txt"
```

### Check Update Status

```bash
novacom run "file://bin/cat /var/lib/software/SessionFiles/update_status.txt"
```

Success looks like:
```
0
updatefsinfo_1.0.0_all
0
0
com.example.mypackage_1.0.0_all
0
0
```

---

## Troubleshooting

### "E0060004" - Package Installation Failed

**Cause:** Usually a filename mismatch between session files and actual files.

**Fix:**
1. Check filenames match exactly:
   ```bash
   novacom run "file://bin/ls /var/lib/update/"
   novacom run "file://bin/cat /var/lib/software/SessionFiles/update_list.txt"
   ```
2. Re-create session files with correct filenames

**Test package directly:**
```bash
novacom run "file://usr/bin/mmipkg install /var/lib/update/your-package.ipk"
```

### Device Stuck in OTA Ramdisk

**Symptoms:** Device shows HP logo, novacom shows device but filesystem looks different.

**Fix:**
```bash
# Restore normal boot
novacom run "file://bin/ln -sf uImage-2.6.35-palm-tenderloin /rootfs/boot/uImage"

# Clear updating flag
novacom run "file://bin/rm /rootfs/var/lib/software/updating"

# Reboot
novacom run "file://sbin/reboot"
```

### Package Rejected by ipkg

**Symptoms:** `ipkg install` returns error 22 or "invalid package"

**Fix:** Ensure control file has required webOS fields:
```
webOS-Package-Format-Version: 2
webOS-Packager-Version: 3.0.5b38
```

### make-update-uimage Fails

**Check the log:**
```bash
novacom run "file://bin/cat /var/log/uimage.log"
```

**Common issues:**
- updatefsinfo package missing or not first in update_list.txt
- Insufficient space in /boot or /tmp
- Corrupt package file

---

## Quick Reference

### File Locations

| File | Purpose |
|------|---------|
| `/var/lib/update/*.ipk` | Downloaded/staged packages |
| `/var/lib/software/SessionFiles/update_list.txt` | Package paths (no /rootfs) |
| `/var/lib/software/SessionFiles/install_list.txt` | Package paths (with /rootfs) |
| `/var/lib/software/updating` | Flag file (1=pending) |
| `/var/lib/software/SessionFiles/update_status.txt` | Results |
| `/boot/update-uimage` | OTA boot ramdisk |
| `/boot/uImage` | Symlink to active kernel |
| `/var/log/uimage.log` | make-update-uimage log |

### Useful Commands

```bash
# List installed packages
novacom run "file://usr/bin/ipkg list_installed"

# Get package info
novacom run "file://usr/bin/ipkg info packagename"

# Install package directly (no OTA)
novacom run "file://usr/bin/ipkg install /path/to/package.ipk"

# Remove package
novacom run "file://usr/bin/ipkg remove packagename"

# Check device storage
novacom run "file://bin/df -h"
```

---

## Alternative: Direct Installation (No OTA)

For quick testing, skip the full OTA process:

```bash
# Upload package
novacom put file:///tmp/mypackage.ipk < mypackage.ipk

# Install directly
novacom run "file://usr/bin/ipkg install /tmp/mypackage.ipk"

# Or using mmipkg (what PmUpdater uses)
novacom run "file://usr/bin/mmipkg install /tmp/mypackage.ipk"
```

This installs immediately without rebooting, but doesn't go through the full OTA validation/backup process.
