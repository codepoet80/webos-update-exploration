# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains a replacement OMA DM (Open Mobile Alliance Device Management) server for HP TouchPad devices running webOS 3.0.5. The original Palm/HP update servers at `ps.palmws.com` have been decommissioned, so this server allows deploying custom updates to physical devices via the native Updates app.

## Development Commands

```bash
# Install dependencies
cd webos-update-server
pip install -r requirements.txt

# Run the server (starts on http://0.0.0.0:8080)
python server.py

# Rescan packages directory via API
curl -X POST http://localhost:8080/packages/scan

# Health check
curl http://localhost:8080/status

# View active sessions (debug)
curl http://localhost:8080/sessions
```

## Architecture

### Server Components (`webos-update-server/`)

```
server.py          # FastAPI main app, OMA DM endpoint handler
config.py          # Server settings, SyncML status/alert codes

wbxml/             # WAP Binary XML codec
├── codec.py       # WBXML encoder/decoder (binary ↔ XML)
└── tokens.py      # SyncML 1.2 token tables

syncml/            # SyncML protocol layer
├── parser.py      # Parse incoming SyncML messages
├── builder.py     # Build SyncML responses
├── auth.py        # HMAC-MD5 authentication
└── session.py     # Session state management

dm/                # Device management logic
├── tree.py        # DM tree operations
└── update.py      # Package management, update availability
```

### Protocol Flow

1. Device sends SyncML message (WBXML-encoded) to `/palmcsext/swupdateserver`
2. Server decodes WBXML → XML, parses SyncML commands
3. Server processes commands (Alert, Get, Results, Replace, Status)
4. Server builds response with Status + commands (Get device info, Replace package URL, Exec download)
5. Device downloads IPK from `/packages/<filename>`

### Device Deployment (`device-patch/`)

- `DmTree.xml` - Modified device configuration pointing to local server
- `deploy.sh` - Script to push config to TouchPad via novacom or SSH

### Package System

Packages live in `webos-update-server/packages/`:
- `manifest.json` - Package registry with metadata, checksums, version targeting
- `*.ipk` - Debian-style packages (ar archives with control.tar.gz + data.tar.gz)

## Key Protocol Details

- **Endpoint**: POST `/palmcsext/swupdateserver`
- **Encoding**: SyncML 1.2 in WBXML (binary) or XML
- **Auth**: HMAC-MD5 via `x-syncml-hmac` header
- **Default credentials**: username=`guest`, password=`guestpassword`
- **Server ID**: Configured in `config.py` as `SERVER_ID`

## Device Configuration Reference

The TouchPad stores its DM configuration at `/usr/share/omadm/DmTree.xml`. Key paths in the DM tree:

- `./DevInfo/*` - Device info (DevId, Man, Mod, FwV, SwV, HwV)
- `./Software/Build` - Current OS build version
- `./Software/Package/*` - Package info (PkgURL, PkgName, PkgVersion, PkgSize)
- `./Software/Operations/DownloadAndInstall` - Exec target to trigger update

## Creating IPK Packages

### Required Control File Fields

webOS ipkg requires specific fields beyond standard Debian format:

```
Package: com.palm.mypackage
Version: 1.0.0
Section: misc
Priority: optional
Architecture: all
Installed-Size: 1
Maintainer: Your Name <email@example.com>
Description: Package description here.
webOS-Package-Format-Version: 2
webOS-Packager-Version: 3.0.5b38
```

**Critical fields:**
- `webOS-Package-Format-Version: 2` - Required for ipkg to accept the package
- `webOS-Packager-Version: 3.0.5b38` - Required for ipkg to accept the package
- `Installed-Size` - Required field
- `com.palm.*` prefix gives special system privileges

### Building IPK Packages

```bash
# Structure
mkdir -p my-package/{CONTROL,data}

# CONTROL/control (required - see format above)
# CONTROL/postinst (optional post-install script, must be executable)

# data/ mirrors device filesystem with ./ prefix
# e.g., data/media/internal/test.txt → /media/internal/test.txt

# Build with correct format:
echo "2.0" > debian-binary

# Control tar MUST have ./ prefix and root ownership
cd CONTROL && tar --uid=0 --gid=0 -czf ../control.tar.gz ./control ./postinst && cd ..

# Data tar MUST have ./ prefix and root ownership
cd data && tar --uid=0 --gid=0 -czf ../data.tar.gz ./media && cd ..

# Create IPK (order matters: debian-binary first)
ar -cr my-package_1.0.0_all.ipk debian-binary control.tar.gz data.tar.gz
```

### Build Script

Use `webos-update-server/packages/build-ota.sh` to build properly formatted IPKs:
```bash
cd webos-update-server/packages
./build-ota.sh
```

## Direct Update API (Bypasses OmaDm)

The server provides direct REST endpoints that bypass the OMA DM protocol, useful for WiFi-only devices where OmaDm fails due to missing carrier detection:

```bash
# Check for updates
curl "http://SERVER:8080/api/updates/check?build=Nova-3.0.5-86"

# Get package URLs
curl "http://SERVER:8080/api/updates/urls?build=Nova-3.0.5-86"
```

### Device-side Update Script

`device-scripts/direct-update.sh` downloads packages and creates session files:
```bash
# On device:
./direct-update.sh http://192.168.10.20:8080 -y
/usr/share/ota-scripts/make-update-uimage
reboot
```

## OTA Update Process - FULLY WORKING ✓

The complete OTA update mechanism has been reverse-engineered and is fully functional.

### Quick Start - Full OTA Update

```bash
# 1. Build packages (on host)
cd webos-update-server/packages/ota-build
./build-ota.sh

# 2. Upload packages to device
novacom put file:///var/lib/update/updatefsinfo_3.0.5-test1_all.ipk < updatefsinfo_3.0.5-test1_all.ipk
novacom put file:///var/lib/update/com.palm.updatetest_1.0.0_all.ipk < com.palm.updatetest_1.0.0_all.ipk

# 3. Create session files (paths must match filenames exactly!)
echo '/var/lib/update/updatefsinfo_3.0.5-test1_all.ipk
/var/lib/update/com.palm.updatetest_1.0.0_all.ipk' | novacom put file:///var/lib/software/SessionFiles/update_list.txt

echo '/rootfs/var/lib/update/updatefsinfo_3.0.5-test1_all.ipk
/rootfs/var/lib/update/com.palm.updatetest_1.0.0_all.ipk' | novacom put file:///var/lib/software/SessionFiles/install_list.txt

# 4. Set updating flag
echo '1' | novacom put file:///var/lib/software/updating

# 5. Create update image and reboot
novacom run file:///usr/share/ota-scripts/make-update-uimage
novacom run file:///sbin/reboot
```

### Session Files (CRITICAL)

| File | Purpose | Path Format |
|------|---------|-------------|
| `update_list.txt` | Used by make-update-uimage | `/var/lib/update/package.ipk` |
| `install_list.txt` | Used by PmUpdater in ramdisk | `/rootfs/var/lib/update/package.ipk` |
| `updating` | Flag file | Must contain `1` |
| `update_status.txt` | Result codes | Created by PmUpdater |

**CRITICAL**: Filenames in session files must EXACTLY match files in `/var/lib/update/`!

### OTA Flow Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. PREPARATION (on running system)                               │
├──────────────────────────────────────────────────────────────────┤
│ • Packages uploaded to /var/lib/update/                          │
│ • Session files created in /var/lib/software/SessionFiles/       │
│ • updating flag set to 1                                         │
│ • make-update-uimage creates /boot/update-uimage (~9MB)          │
│ • /boot/uImage symlinked to update-uimage                        │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼ reboot
┌──────────────────────────────────────────────────────────────────┐
│ 2. OTA RAMDISK BOOT                                              │
├──────────────────────────────────────────────────────────────────┤
│ • Device boots from update-uimage (minimal ramdisk)              │
│ • Root filesystem mounted at /rootfs                             │
│ • /usr/share/ota-scripts/ota.sh orchestrates update              │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ 3. PRE-UPDATE (ota.sh → pre-update script)                       │
├──────────────────────────────────────────────────────────────────┤
│ • Saves user data to /media/internal/.save_for_software_update/  │
│ • Progress file set to 1                                         │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ 4. PACKAGE INSTALLATION (PmUpdater)                              │
├──────────────────────────────────────────────────────────────────┤
│ • PmUpdater reads /rootfs/var/lib/software/SessionFiles/         │
│ • Calls mmipkg to install packages from install_list.txt         │
│ • Runs postinst scripts for each package                         │
│ • Writes results to update_status.txt (0 = success)              │
│ • Progress file set to 2                                         │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ 5. POST-UPDATE (ota.sh → post-update script)                     │
├──────────────────────────────────────────────────────────────────┤
│ • Filesystem checks (e2fsck)                                     │
│ • Partition resizing if needed                                   │
│ • Data migration                                                 │
│ • /boot/uImage symlink restored to normal kernel                 │
│ • updating flag cleared                                          │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼ reboot
┌──────────────────────────────────────────────────────────────────┐
│ 6. NORMAL BOOT                                                   │
├──────────────────────────────────────────────────────────────────┤
│ • Device boots normally from uImage-2.6.35-palm-tenderloin       │
│ • Packages are installed and functional                          │
└──────────────────────────────────────────────────────────────────┘
```

### Progress States

| State | Meaning |
|-------|---------|
| 0 | Begin (initial state) |
| 1 | Pre-update/dataexport completed |
| 2 | Package installation completed, begin post-update |
| -2 | Installation failed, retrying |

### update_status.txt Format

Success:
```
0
packagename_version_arch
0
0
```

Failure:
```
E0060004
packagename_version_arch
0
E0060004
```

### Error Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| E0060004 | Package installation failed |
| E0060011 | Update image creation failed |
| E0060012 | Data save/restore error |
| E0060013 | Data export failed |
| E0060014 | resizefat error |
| E0060015 | pre-update script not found |

### PmUpdater Details

PmUpdater is proprietary (not in HP OSS) but uses **mmipkg** internally:

```bash
# mmipkg usage (same as what PmUpdater calls)
mmipkg [-v] [-o root] [-n] [-r] <install|remove> <list of ipks>

# Options:
#   -v    Verbose
#   -o    Alternate root path (e.g., -o /rootfs)
#   -n    No scripts (skip postinst/prerm)
#   -r    Reinstall
```

### Alternative: Direct Installation (No Reboot)

Skip the full OTA and install packages directly on running system:

```bash
# Using mmipkg (what PmUpdater uses)
mmipkg install /var/lib/update/package.ipk

# Using ipkg (standard)
ipkg install /var/lib/update/package.ipk
```

### Troubleshooting

**E0060004 - Package installation failed**
- Check that filenames in session files match actual files in /var/lib/update/
- Verify packages have correct webOS control file fields
- Test with `mmipkg install <package>` on running system first

**Device stuck in OTA ramdisk**
- Connect via novacom and check `/rootfs/var/log/progress`
- Check `/rootfs/var/lib/software/SessionFiles/update_status.txt`
- Manually restore uImage: `ln -sf uImage-2.6.35-palm-tenderloin /rootfs/boot/uImage`

**make-update-uimage fails**
- Ensure updatefsinfo package is first in update_list.txt
- Check /var/log/uimage.log for details

---

# HP TouchPad webOS 3.0.5 Reference

The following sections document the webOS system for reference when building updates or understanding device behavior.

## Device Information

- **Codename:** Topaz
- **CPU:** Qualcomm MSM8660 (ARMv7, dual-core Scorpion)
- **Display:** 1024x768
- **Storage:** eMMC (`/dev/mmcblk0`)
- **OS Version:** webOS 3.0.5 (build 86)
- **Build Date:** December 21, 2011

## Partition Layout

Uses MBR with extended partitions and LVM. Key partitions:

| Partition | Type | Mount Point |
|-----------|------|-------------|
| p13 | ext3 | /boot (32MB) |
| p14 | LVM | Volume group "store" |

### LVM Volumes (store)

| Volume | Type | Size | Mount Point |
|--------|------|------|-------------|
| root | ext3 | 568MB | / (read-only) |
| var | ext3 | 64MB | /var |
| update | ext3 | 16MB | /var/lib/update |
| log | ext3 | 24MB | /var/log |
| mojodb | ext3 | 144-512MB | (encrypted) /var/db |
| filecache | ext3 | 136MB | (encrypted) /var/file-cache |
| media | FAT32 | * | /media/internal |
| swap | swap | 512MB | - |

## System Architecture

### Core Components

1. **LunaSysMgr** (`/usr/bin/LunaSysMgr`) - Qt/C++ window compositor and card manager
2. **Luna Service Bus (ls2)** - IPC via `palm://servicename` with JSON messages
3. **MojoDB** - Encrypted JSON document database
4. **Node.js Services** - Backend services at `/usr/palm/nodejs/`

### Application Locations

- `/usr/palm/applications/` - System apps (reverse-domain naming)
- `/media/cryptofs/apps/` - Third-party installed apps
- `/usr/palm/services/` - Background services
- `/usr/palm/frameworks/` - Mojo and Enyo frameworks

## Update System Internals

### Native Components

- `/usr/bin/UpdateDaemon` - Luna service handling update lifecycle
- `/usr/bin/OmaDm` - OMA DM protocol client
- `/usr/share/omadm/DmTree.xml` - DM tree configuration
- `/usr/share/ota-scripts/` - Pre/post update shell scripts

### Luna Service API (`palm://com.palm.update/`)

| Method | Purpose |
|--------|---------|
| CheckForUpdate | Query server for updates |
| GetStatusApp | Get update status (subscribable) |
| DownloadNow | Start/resume download |
| InstallNow | Begin installation |
| CancelDownload | Cancel download |

### Update States

Checking → UpToDate | Waiting → Downloading → Validating → Available → Countdown → InstallBegun → InstallSuccessful/InstallFailed

### Installation Process

1. **Pre-update** (`pre-update`) - Backs up user data to `/media/internal/.save_for_software_update/`
2. **Image creation** (`make-update-uimage`) - Builds ramdisk at `/boot/update-uimage`
3. **Installation** - Reboots into ramdisk, runs `PmUpdater`
4. **Post-update** (`post-update`) - Filesystem checks, partition resize, data restore

### Key Runtime Paths

| Path | Purpose |
|------|---------|
| /var/lib/update/ | Downloaded packages |
| /var/lib/software/SessionFiles/ | Update state files |
| /var/lib/software/SessionFiles/urls | Package URLs |
| /var/lib/software/SessionFiles/update_list.txt | Package manifest |

## Useful Device Paths

| Path | Description |
|------|-------------|
| /media/internal/ | User storage (FAT32, writable) |
| /var/luna/preferences/ | System preferences |
| /var/palm/data/ | App data |
| /var/log/messages | System log |

## Development Access

```bash
# Enable developer mode: Just Type → "webos20090606"

# USB networking (after dev mode)
ssh root@172.16.42.1

# Remount root for changes
mount -o remount,rw /
# ... make changes ...
mount -o remount,ro /
```
