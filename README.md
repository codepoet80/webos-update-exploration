# webOS Update Server

A local OMA DM server replacement for HP TouchPad devices running webOS 3.0.5.

## Background

The HP TouchPad was released in 2011 running webOS, an elegant Linux-based mobile operating system originally developed by Palm. The device checked for software updates via Palm/HP's OMA Device Management servers at `ps.palmws.com`. These servers have long been decommissioned, leaving devices unable to receive updates through the built-in Updates app.

This project implements a fully compatible replacement server, enabling you to deploy custom updates to physical TouchPad devices using the native update mechanism.

## Features

- **Full OMA DM/SyncML 1.2 Protocol** - Complete implementation of the device management protocol
- **WBXML Support** - Encodes/decodes WAP Binary XML used by the device
- **HMAC-MD5 Authentication** - Implements the `syncml:auth-MAC` authentication scheme
- **Session Management** - Tracks device sessions and state
- **Package Hosting** - Serves IPK packages with resumable download support
- **Sample Test Package** - Included package to verify your setup works

## Requirements

- Python 3.8+
- HP TouchPad with webOS 3.0.x
- Developer mode enabled on the device
- Network connectivity between server and device

## Quick Start

### 1. Install Dependencies

```bash
cd webos-update-server
pip install -r requirements.txt
```

### 2. Start the Server

```bash
python server.py
```

The server starts on `http://0.0.0.0:8080` by default.

### 3. Configure Your TouchPad

The device needs to be redirected from the defunct Palm servers to your local server. Use the deployment script in the `device-patch` folder:

```bash
cd ../device-patch
./deploy.sh 192.168.1.100  # Replace with your server's IP address
```

Or deploy manually - see [Device Configuration](#device-configuration) below.

### 4. Test the Update

A sample test package is included. When installed, it creates `/media/internal/UpdateApplied.txt` on the device to confirm everything works.

Open the **Updates** app on your TouchPad. It should connect to your server and offer the test update.

## Device Configuration

### Prerequisites

- **Developer Mode**: On the TouchPad, go to `Just Type` and enter `webos20090606` to enable developer mode
- **Access Method**: Either USB (via novacom/Novaterm) or SSH over WiFi

### Automatic Deployment

```bash
cd device-patch
./deploy.sh YOUR_SERVER_IP
```

The script will:
1. Connect to your TouchPad
2. Backup the original configuration
3. Install the modified DmTree.xml pointing to your server

### Manual Deployment

1. Connect to your TouchPad via SSH or novacom:
   ```bash
   ssh root@172.16.42.1        # USB networking
   # or
   novacom -t open tty://      # novacom terminal
   ```

2. Remount the filesystem as read-write:
   ```bash
   mount -o remount,rw /
   ```

3. Backup the original file:
   ```bash
   cp /usr/share/omadm/DmTree.xml /usr/share/omadm/DmTree.xml.backup
   ```

4. Edit `/usr/share/omadm/DmTree.xml` and change:
   ```xml
   <!-- Find this line: -->
   <value>https://ps.palmws.com/palmcsext/swupdateserver</value>

   <!-- Change to: -->
   <value>http://YOUR_SERVER_IP:8080/palmcsext/swupdateserver</value>
   ```

   Also update the port from `443` to `8080`.

5. Remount as read-only:
   ```bash
   mount -o remount,ro /
   ```

### Restoring Original Configuration

```bash
mount -o remount,rw /
cp /usr/share/omadm/DmTree.xml.backup /usr/share/omadm/DmTree.xml
mount -o remount,ro /
```

## Creating Update Packages

### IPK Package Format

webOS uses IPK packages, which are standard Debian-style packages (ar archives). Each IPK contains:

- `debian-binary` - Package format version ("2.0")
- `control.tar.gz` - Package metadata and scripts
- `data.tar.gz` - Files to install on the device

### Building a Simple Package

1. Create the directory structure:
   ```bash
   mkdir -p my-package/{CONTROL,data}
   ```

2. Create `CONTROL/control`:
   ```
   Package: com.example.mypackage
   Version: 1.0.0
   Section: misc
   Priority: optional
   Architecture: all
   Maintainer: Your Name <you@example.com>
   Description: My custom update package
   ```

3. Create `CONTROL/postinst` (post-installation script):
   ```bash
   #!/bin/sh
   echo "Package installed!" > /media/internal/install-log.txt
   exit 0
   ```

4. Make scripts executable:
   ```bash
   chmod +x CONTROL/postinst
   ```

5. Add any files to install in `data/` (mirroring the device filesystem structure)

6. Build the IPK:
   ```bash
   echo "2.0" > debian-binary
   cd CONTROL && tar czf ../control.tar.gz . && cd ..
   cd data && tar czf ../data.tar.gz . && cd ..
   ar rc my-package_1.0.0_all.ipk debian-binary control.tar.gz data.tar.gz
   ```

7. Move to packages directory and update manifest:
   ```bash
   mv my-package_1.0.0_all.ipk ../packages/
   ```

### Package Manifest

Edit `packages/manifest.json` to register your packages:

```json
{
  "packages": [
    {
      "name": "com.example.mypackage",
      "version": "1.0.0",
      "filename": "my-package_1.0.0_all.ipk",
      "size": 1234,
      "md5": "abc123...",
      "description": "My custom update",
      "min_version": "",
      "target_build": "Nova-99.0.0"
    }
  ]
}
```

**Fields:**
- `name` - Package identifier
- `version` - Package version
- `filename` - IPK filename in packages directory
- `size` - File size in bytes
- `md5` - MD5 checksum of the file
- `description` - Shown to user
- `min_version` - Minimum device build required (optional)
- `target_build` - Target build version; device must be below this to receive update

**Tip:** Use `target_build: "Nova-99.0.0"` to offer the update to all devices (since no device has this version).

### Auto-scanning Packages

After adding new packages, trigger a rescan:
```bash
curl -X POST http://localhost:8080/packages/scan
```

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Server information |
| `/status` | GET | Health check |
| `/palmcsext/swupdateserver` | POST | OMA DM SyncML endpoint |
| `/packages/<filename>` | GET | Download package (supports range requests) |
| `/packages/manifest.json` | GET | Package manifest |
| `/packages/scan` | POST | Rescan packages directory |
| `/sessions` | GET | List active sessions (debug) |

## Configuration

Edit `config.py` to customize server settings:

```python
SERVER_HOST = "0.0.0.0"      # Bind address
SERVER_PORT = 8080            # Port number
SERVER_ID = "webos-update-server"
PACKAGES_DIR = "packages"     # Package storage
SESSION_TIMEOUT = 3600        # Session timeout (seconds)
DEBUG = True                  # Enable debug logging
```

## Protocol Overview

The server implements the OMA Device Management protocol:

```
HP TouchPad                           Your Server
     |                                     |
     |  1. POST SyncML (Alert 1201)        |
     |  ─────────────────────────────────> |  Session init
     |                                     |
     |  2. SyncML Response                 |
     |  <───────────────────────────────── |  Request device info
     |     (Status + Get DevInfo)          |
     |                                     |
     |  3. POST SyncML (Results)           |
     |  ─────────────────────────────────> |  Device info response
     |                                     |
     |  4. SyncML Response                 |
     |  <───────────────────────────────── |  Update available!
     |     (Replace + Exec)                |  (package URL + install cmd)
     |                                     |
     |  5. GET /packages/update.ipk        |
     |  ═════════════════════════════════> |  Download package
     |                                     |
     |  [Device installs package]          |
     |                                     |
```

## Troubleshooting

### Device doesn't connect to server

1. **Check network**: Ensure device and server are on the same network
2. **Verify IP**: Confirm the IP in DmTree.xml matches your server
3. **Firewall**: Ensure port 8080 is open
4. **Test manually**: `curl http://YOUR_SERVER:8080/status`

### Server shows connection but no update offered

1. **Check manifest**: Ensure package is listed in `manifest.json`
2. **Version check**: Verify `target_build` is higher than device's current build
3. **Rescan**: `curl -X POST http://localhost:8080/packages/scan`

### WBXML parsing errors

1. Enable debug mode in `config.py`: `DEBUG = True`
2. Check server logs for raw request data
3. Verify device is sending to correct endpoint

### Device shows "No update available"

This is normal if:
- No packages in manifest
- Device build is at or above `target_build`
- Package `min_version` requirement not met

## Project Structure

```
webos-update-server/
├── server.py              # FastAPI main application
├── config.py              # Server configuration
├── requirements.txt       # Python dependencies
├── README.md              # This file
│
├── wbxml/                 # WBXML binary XML codec
│   ├── __init__.py
│   ├── codec.py           # Encoder/decoder implementation
│   └── tokens.py          # SyncML 1.2 token tables
│
├── syncml/                # SyncML protocol handler
│   ├── __init__.py
│   ├── parser.py          # Message parser
│   ├── builder.py         # Response builder
│   ├── auth.py            # HMAC-MD5 authentication
│   └── session.py         # Session management
│
├── dm/                    # Device management logic
│   ├── __init__.py
│   ├── tree.py            # DM tree operations
│   └── update.py          # Update package management
│
└── packages/              # Update packages
    ├── manifest.json      # Package registry
    └── *.ipk              # IPK package files
```

## Technical References

- [OMA Device Management Protocol](https://www.openmobilealliance.org/release/DM/V1_2-20070209-A/)
- [SyncML Representation Protocol](https://www.openmobilealliance.org/release/Common/V1_2-20070209-A/)
- [WBXML Specification](https://www.w3.org/TR/wbxml/)
- [webOS Internals Wiki](https://www.webos-internals.org/)

## License

MIT License - See LICENSE file for details.

## Acknowledgments

- The webOS community for keeping these devices alive
- HP/Palm for creating webOS
- webOS Internals for documentation and tools
