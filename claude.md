# HP TouchPad webOS 3.0.5 Reference

## Device Information

- **Codename:** Topaz
- **CPU:** Qualcomm MSM8660 (ARMv7, dual-core Scorpion)
- **Display:** 1024x768
- **Storage:** eMMC (`/dev/mmcblk0`)
- **OS Version:** webOS 3.0.5 (build 86)
- **Build Date:** December 21, 2011

## Archive Structure

```
webosdoctorp305hstnhwifi.jar
├── com/palm/novacom/         # Java Doctor tool classes
├── META-INF/
└── resources/
    ├── webOS.tar             # Main OS image (201MB)
    ├── hp.tar                # HP customization packages (21MB)
    ├── NovacomInstaller_*    # USB driver installers (Win/Mac)
    └── *.png, *.html         # Doctor UI assets
```

### webOS.tar Contents

```
webOS/
├── boot-topaz.bin                        # Bootloader
├── nova-installer-image-topaz.uImage     # Installer kernel (14MB)
├── nova-cust-image-topaz.rootfs.tar.gz   # Root filesystem (186MB)
├── topaz.xml                             # Partition/install configuration
├── installer.xml                         # Install metadata
└── *.tga                                 # Boot screen images
```

### hp.tar Contents

HP-specific customization IPK packages:
- `audiod-config-eu` - EU audio configuration
- `crotest-images` - CRO test images
- `palmcustomizationinfo-hp` - HP branding
- `sweatshop-hp-topaz` - HP factory tools

## Partition Layout

Defined in `webOS/topaz.xml`. Uses MBR with extended partitions and LVM.

### Physical Partitions

| Partition | Type | Size | Purpose |
|-----------|------|------|---------|
| p1 | FAT | 1MB | fat.bin |
| p2 | CFG_DATA | 500KB | rpmsbl.mbn |
| p3 | SPBL | 1.5MB | spbl.mbn |
| p5 | APPSSBL | 500KB | rpm.mbn |
| p6 | QCSBL | 500KB | ssbl.mbn |
| p7 | EFS2 | 65MB | Modem filesystem |
| p8 | FOTA | 2.5MB | emmc_appsboot.mbn |
| p9 | APPS | 10MB | boot.img (kernel) |
| p10 | OEMSBL | 500KB | tz.mbn (TrustZone) |
| p11-12 | MODEM_ST | 3MB each | Modem storage |
| p13 | ext3 | 32MB | /boot |
| p14 | LVM | * | Volume group "store" |

### LVM Volumes (store)

| Volume | Type | Size | Mount Point |
|--------|------|------|-------------|
| root | ext3 | 568MB | / (read-only) |
| var | ext3 | 64MB | /var |
| update | ext3 | 16MB | /var/lib/update |
| log | ext3 | 24MB | /var/log |
| mojodb | ext3 | 144-512MB* | (encrypted) /var/db |
| filecache | ext3 | 136MB | (encrypted) /var/file-cache |
| media | FAT32 | * | /media/internal |
| swap | swap | 512MB | - |

*mojodb size varies by device storage capacity (8GB=144MB, 16GB+=256MB, 64GB=512MB)

## Filesystem Structure

Standard Linux FHS with webOS-specific additions:

```
/
├── bin/                    # Core utilities (busybox)
├── boot/                   # Kernel, device tree
├── etc/
│   ├── palm/              # webOS configuration
│   │   └── luna.conf      # LunaSysMgr settings
│   └── init.d/            # Init scripts
├── lib/                    # Shared libraries (glibc, Qt)
├── sbin/                   # System binaries
├── usr/
│   ├── bin/
│   │   └── LunaSysMgr     # Main UI compositor (ARM ELF)
│   ├── lib/
│   │   └── luna/          # Luna libraries
│   │       ├── luna-media/
│   │       ├── luna-network/
│   │       └── system/
│   ├── palm/              # webOS applications and services
│   │   ├── applications/  # User-facing apps
│   │   ├── services/      # Background services
│   │   ├── frameworks/    # Mojo, Enyo, etc.
│   │   ├── sysmgr/        # System manager resources
│   │   └── nodejs/        # Node.js runtime
│   └── plugins/           # Browser plugins
└── var/
    ├── db/                # MojoDB (encrypted)
    ├── luna/              # Luna runtime data
    └── palm/              # Palm runtime data
```

## System Architecture

### Core Components

1. **LunaSysMgr** (`/usr/bin/LunaSysMgr`)
   - Qt/C++ application
   - Window compositor and card manager
   - Handles gestures, notifications, app lifecycle
   - Config: `/etc/palm/luna.conf`

2. **Luna Service Bus (ls2)** (`/usr/palm/ls2/`)
   - IPC mechanism for all system services
   - JSON-based message passing
   - Services register at `palm://servicename`

3. **MojoDB**
   - JSON document database
   - Stores app data, contacts, messages, etc.
   - Encrypted on-device

4. **Node.js Services**
   - Backend services written in JavaScript
   - Run via `/usr/palm/nodejs/`

### Application Framework

#### Mojo (Original webOS framework)
- Location: `/usr/palm/frameworks/mojo/`
- MVC architecture for HTML5 apps
- Widgets, scenes, stages model
- Used by most stock apps

#### Enyo 1.0 (TouchPad-era framework)
- Location: `/usr/palm/frameworks/enyo/`
- Component-based architecture
- Better suited for tablet UI
- Versions: 0.10, 1.0

## Application Structure

Apps live in `/usr/palm/applications/` with reverse-domain naming:

```
com.palm.app.browser/
├── appinfo.json          # App manifest (required)
├── index.html            # Entry point
├── icon.png              # App icon (64x64)
├── icon-256x256.png      # Splash icon
├── depends.js            # Framework dependencies
├── source/               # JavaScript source
├── css/                  # Stylesheets
├── images/               # Image assets
└── resources/            # Localization
```

### appinfo.json Format

```json
{
  "id": "com.palm.app.browser",
  "version": "1.0.0",
  "vendor": "HP",
  "type": "web",
  "main": "index.html",
  "title": "Web",
  "icon": "icon.png",
  "splashicon": "icon-256x256.png"
}
```

## Pre-installed Applications

| App ID | Name |
|--------|------|
| com.palm.app.browser | Web Browser |
| com.palm.app.contactsmojo | Contacts |
| com.palm.app.phone | Phone |
| com.palm.app.videoplayer | Videos |
| com.palm.app.streamingmusicplayer | Music |
| com.palm.app.skype | Skype |
| com.palm.app.wifi | Wi-Fi Settings |
| com.palm.app.bluetooth | Bluetooth Settings |
| com.palm.app.deviceinfo | Device Info |
| com.palm.app.updates | System Updates |
| com.palm.app.firstuse | First Use Setup |

## Services

Background services in `/usr/palm/services/`:

| Service | Purpose |
|---------|---------|
| com.palm.service.accounts | Account management |
| com.palm.service.contacts.* | Contact sync (Google, Facebook, etc.) |
| com.palm.service.calendar.* | Calendar sync |
| com.palm.service.photos.* | Photo services |
| com.palm.service.backup | Backup/restore |
| com.palm.service.bluetooth.spp | Bluetooth serial |

## Key Configuration Files

- `/etc/palm/luna.conf` - LunaSysMgr settings (display, memory, paths)
- `/etc/palm/launcher3.conf` - App launcher config
- `/usr/palm/command-resource-handlers.json` - URL/MIME handlers
- `/usr/palm/default-dock-positions.json` - Default dock apps

## Development Notes

### Luna Service Calls

Apps communicate with system via Luna bus:
```javascript
this.controller.serviceRequest('palm://com.palm.wifi', {
    method: 'getstatus',
    onSuccess: function(response) { ... }
});
```

### Package Format

Apps distributed as IPK files (Debian ar archive):
```
package.ipk
├── debian-binary
├── control.tar.gz
│   ├── control
│   ├── postinst
│   └── prerm
└── data.tar.gz
    └── usr/palm/applications/com.example.app/
```

### USB Communication

Novacom protocol used for:
- Device recovery (Doctor)
- Developer mode file transfer
- Remote shell access

Drivers in `resources/NovacomInstaller_*`

## Useful Paths

| Path | Description |
|------|-------------|
| `/media/internal/` | User storage (FAT32) |
| `/media/cryptofs/apps/` | Installed 3rd-party apps |
| `/var/luna/preferences/` | System preferences |
| `/var/palm/data/` | App data |
| `/var/log/messages` | System log |

---

## System Update Mechanism

### Overview

webOS used an OTA (Over-The-Air) update system based on the **OMA DM** (Open Mobile Alliance Device Management) protocol. The system consisted of:

1. **Updates App** (`com.palm.app.updates`) - User-facing Enyo app
2. **UpdateDaemon** (`/usr/bin/UpdateDaemon`) - Native C++ daemon
3. **OmaDm Client** (`/usr/bin/OmaDm`) - OMA DM protocol client
4. **OTA Scripts** - Shell scripts for installation (`/usr/share/ota-scripts/`)

### Update Server

The device contacted Palm/HP servers at:
```
https://ps.palmws.com/palmcsext/swupdateserver
```

Configuration in `/usr/share/omadm/DmTree.xml`:
- Server ID: `omadm.swupdate.palm.com`
- Port: 443 (HTTPS)
- Auth: HMAC with guest credentials

### Update Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Updates App    │────▶│  UpdateDaemon   │────▶│    OmaDm        │
│  (Enyo UI)      │     │  (luna service) │     │  (DM client)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                │                        │
                                ▼                        ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │  Download Svc   │     │  Palm Servers   │
                        │  (curl-based)   │     │  ps.palmws.com  │
                        └─────────────────┘     └─────────────────┘
```

### Luna Service API

The UpdateDaemon exposed these methods via `palm://com.palm.update/`:

| Method | Purpose |
|--------|---------|
| `CheckForUpdate` | Query server for available updates |
| `GetStatusApp` | Get current update status (subscribable) |
| `DownloadNow` | Start/resume update download |
| `InstallNow` | Begin update installation |
| `CancelDownload` | Cancel in-progress download |
| `DismissedUpdate` | Mark optional update as deferred |
| `TaskCheck` | Weekly scheduled check callback |
| `ServerPush` | Handle push notifications |

### Update States

The system tracked these states:

| State | Description |
|-------|-------------|
| `Checking` | Querying server for updates |
| `UpToDate` | No updates available |
| `Waiting` | Update available, waiting to download |
| `Downloading` | Download in progress |
| `Validating` | Verifying downloaded packages |
| `Available` | Ready to install |
| `Countdown` | Install countdown timer |
| `InstallBegun` | Installation started |
| `InstallSuccessful` | Update completed |
| `InstallFailed` | Update failed |
| `SpaceNeeded` | Insufficient storage |
| `InsufficientCharge` | Battery too low |
| `NetworkFailed` | Network error |
| `InvalidUpdate` | Validation failed |

### Update Priority Levels

- `optional` - User can defer (Update Now / Update Later buttons)
- `default` - Background download, notify when ready
- `forced` - Required update, starts immediately

### Scheduled Checks

Defined in `/etc/palm/activities/com.palm.update/com.palm.update_weeklyTask`:
```json
{
    "activity": {
        "name": "weeklyUpdateCheck",
        "schedule": { "interval": "7d" },
        "callback": { "method": "palm://com.palm.update/TaskCheck" }
    }
}
```

### Delta Updates (ipkgdelta)

The system supported delta/differential updates using `bsdiff`:

- Location: `/usr/share/downloadupdate/ipkgdelta`
- Creates binary patches between IPK versions
- Reduces download size significantly
- Uses MD5 checksums for verification

Operations:
```bash
ipkgdelta diff <old.ipk> <new.ipk> <patch.dipk>   # Create patch
ipkgdelta patch <old.ipk> <new.ipk> <patch.dipk>  # Apply patch
ipkgdelta id <package.ipk>                         # Get package hash
```

### OTA Installation Process

#### 1. Pre-Update (`/usr/share/ota-scripts/pre-update`)
- Saves user data to `/media/internal/.save_for_software_update/`
- Backs up email attachments, Luna data files
- Exports Java-based OS data if upgrading from older version
- Prepares encrypted partition migration if needed

#### 2. Update Image Creation (`make-update-uimage`)
- Creates ramdisk filesystem for update
- Extracts packages from downloaded update
- Validates MD5 checksums
- Builds multi-image uImage (kernel + ramdisk)
- Writes to `/boot/update-uimage`

#### 3. Installation
- Device reboots into update ramdisk
- `PmUpdater` installs IPK packages
- LVM partitions resized if needed
- Encrypted partitions migrated

#### 4. Post-Update (`/usr/share/ota-scripts/post-update`)
- Runs filesystem checks (e2fsck)
- Resizes partitions (var, log, swap, mojodb)
- Sets up encryption for db/filecache
- Runs data migration scripts
- Restores user data

### Key Files and Directories

| Path | Purpose |
|------|---------|
| `/usr/bin/UpdateDaemon` | Main update service daemon |
| `/usr/bin/OmaDm` | OMA DM protocol client |
| `/usr/share/omadm/DmTree.xml` | DM tree with server config |
| `/var/lib/update/` | Downloaded update packages |
| `/var/lib/software/SessionFiles/` | Update state files |
| `/var/lib/software/SessionFiles/urls` | Package download URLs |
| `/var/lib/software/SessionFiles/update_list.txt` | Package manifest |
| `/var/lib/software/SessionFiles/update_status.txt` | Status code file |
| `/boot/update-uimage` | Update boot image |
| `/boot/updatefs-info` | Update filesystem metadata |

### Update Package Structure

Updates consisted of IPK packages downloaded to `/var/lib/update/`:
```
/var/lib/update/
├── data.tar.gz           # Main update data
├── install-first.sh      # Pre-install script
├── *.ipk                 # Individual packages
└── *.dipk                # Delta packages
```

### Error Codes

Written to `/var/lib/software/SessionFiles/update_status.txt`:

| Code | Meaning |
|------|---------|
| E0060011 | Update image creation failed |
| E0060012 | Data save/restore error |
| E0060013 | Data export failed |

### Boot-Level Update Configs

- `/boot/image-update.xml` - Partition layout for image updates
- `/boot/genesis-update.xml` - Bootloader update config (sbl1, sbl2, rpm, tz.mbn)

### WAP Push Handler

The system could receive update notifications via WAP push:
- Handler: `/etc/messagingrouter/waphandlers/updatehandler`
- Endpoint: `palm://com.palm.update/ServerPush`
- Node: `swupdate`
