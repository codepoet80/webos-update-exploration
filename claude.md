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

```bash
# Structure
mkdir -p my-package/{CONTROL,data}

# CONTROL/control (required metadata)
# CONTROL/postinst (optional post-install script)

# data/ mirrors device filesystem
# e.g., data/media/internal/test.txt → /media/internal/test.txt

# Build
echo "2.0" > debian-binary
cd CONTROL && tar czf ../control.tar.gz . && cd ..
cd data && tar czf ../data.tar.gz . && cd ..
ar rc my-package_1.0.0_all.ipk debian-binary control.tar.gz data.tar.gz
```

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
