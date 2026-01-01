# Local webOS Update Server Replacement

## Overview

Build a full-compatibility local OMA DM server to replace the defunct Palm/HP update servers for HP TouchPad devices running webOS 3.0.5. This enables deploying custom updates to physical devices.

## User Requirements

- **Language**: Python (Flask/FastAPI)
- **Testing**: Physical TouchPad available
- **Compatibility**: Full OMA DM protocol with WBXML support
- **Goal**: Deploy custom updates to devices

## Protocol Analysis Summary

### OMA DM Protocol Stack
- **Transport**: HTTPS (port 443) or HTTP
- **Encoding**: SyncML in WBXML (binary) or XML format
- **Auth**: HMAC-MD5 with header `x-syncml-hmac: algorithm=MD5, mac=<hash>, username=<user>`
- **Credentials**: username=`guest`, password=`guestpassword` (hardcoded defaults)

### Original Server
```
https://ps.palmws.com/palmcsext/swupdateserver
```

### Device Configuration
- DM Tree: `/usr/share/omadm/DmTree.xml`
- Update staging: `/var/lib/update/`
- Session files: `/var/lib/software/SessionFiles/`

## Implementation Approach: Full OMA DM Server

### Components to Build

1. **WBXML Codec** (`wbxml/`)
   - WBXML decoder for incoming device messages
   - WBXML encoder for server responses
   - SyncML 1.2 / OMA DM token tables

2. **SyncML Protocol Handler** (`syncml/`)
   - Parse SyncML messages (commands, headers, items)
   - Build SyncML responses
   - Session state management
   - HMAC-MD5 authentication

3. **OMA DM Server** (`server.py`)
   - FastAPI-based HTTP/HTTPS server
   - DM session management
   - Device tree (DmTree) manipulation
   - Update orchestration logic

4. **Package Manager** (`packages/`)
   - Host IPK packages for download
   - Generate manifests with checksums/sizes
   - Support delta packages (.dipk)

5. **Device Configuration** (`device-patch/`)
   - Modified DmTree.xml for local server
   - Deployment scripts/instructions

## File Structure

```
webos-update-server/
├── server.py                    # FastAPI main application
├── config.py                    # Server configuration
├── requirements.txt
├── README.md
│
├── wbxml/
│   ├── __init__.py
│   ├── codec.py                 # WBXML encoder/decoder
│   ├── tokens.py                # SyncML/OMA DM token tables
│   └── test_wbxml.py            # Codec tests
│
├── syncml/
│   ├── __init__.py
│   ├── parser.py                # SyncML message parser
│   ├── builder.py               # SyncML response builder
│   ├── commands.py              # GET/REPLACE/ADD/DELETE/EXEC handlers
│   ├── auth.py                  # HMAC-MD5 authentication
│   └── session.py               # Session state management
│
├── dm/
│   ├── __init__.py
│   ├── tree.py                  # Device Management tree operations
│   └── update.py                # Update orchestration logic
│
├── packages/                    # IPK packages to serve
│   ├── manifest.json            # Package manifest
│   └── *.ipk                    # Update packages
│
├── device-patch/
│   ├── DmTree.xml               # Modified DM tree for device
│   └── deploy.sh                # Deployment helper script
│
└── certs/
    ├── server.crt               # Self-signed certificate
    └── server.key               # Private key
```

## Server Endpoints

```
POST /palmcsext/swupdateserver     # OMA DM SyncML endpoint (WBXML/XML)
GET  /packages/<filename>          # IPK package downloads
GET  /packages/manifest.json       # Package manifest
GET  /status                       # Server health check
GET  /                             # Web UI for management
```

## OMA DM Session Flow

```
Device                                    Server
   |                                         |
   |  1. PKG#1: SessionInit (Alert 1201)     |
   | ───────────────────────────────────────>|
   |                                         |
   |  2. PKG#2: Status + Server Commands     |
   |<─────────────────────────────────────── |
   |     (GET ./DevInfo/*, ./Software/Build) |
   |                                         |
   |  3. PKG#3: Results + Client Status      |
   | ───────────────────────────────────────>|
   |                                         |
   |  4. PKG#4: Update Available (REPLACE)   |
   |<─────────────────────────────────────── |
   |     (./Software/Package/PkgURL = ...)   |
   |     (./Software/Build = new_version)    |
   |                                         |
   |  5. PKG#5: Acknowledge + Final          |
   | ───────────────────────────────────────>|
   |                                         |
   |  6. Device downloads IPK from PkgURL    |
   | ═══════════════════════════════════════>|
   |                                         |
```

## SyncML Message Structure

### Request from Device (PKG#1)
```xml
<SyncML xmlns="SYNCML:SYNCML1.2">
  <SyncHdr>
    <VerDTD>1.2</VerDTD>
    <VerProto>DM/1.2</VerProto>
    <SessionID>1</SessionID>
    <MsgID>1</MsgID>
    <Target><LocURI>https://server/palmcsext/swupdateserver</LocURI></Target>
    <Source><LocURI>IMEI:xxxxx</LocURI></Source>
    <Cred>
      <Meta><Type>syncml:auth-MAC</Type></Meta>
      <Data>base64-hmac-digest</Data>
    </Cred>
  </SyncHdr>
  <SyncBody>
    <Alert>
      <CmdID>1</CmdID>
      <Data>1201</Data>  <!-- Client-initiated session -->
    </Alert>
    <Final/>
  </SyncBody>
</SyncML>
```

### Response from Server (PKG#2)
```xml
<SyncML xmlns="SYNCML:SYNCML1.2">
  <SyncHdr>
    <VerDTD>1.2</VerDTD>
    <VerProto>DM/1.2</VerProto>
    <SessionID>1</SessionID>
    <MsgID>1</MsgID>
    <Target><LocURI>IMEI:xxxxx</LocURI></Target>
    <Source><LocURI>webos-update-server</LocURI></Source>
  </SyncHdr>
  <SyncBody>
    <Status>
      <CmdID>1</CmdID>
      <MsgRef>1</MsgRef>
      <CmdRef>0</CmdRef>
      <Cmd>SyncHdr</Cmd>
      <Data>212</Data>  <!-- Authentication accepted -->
    </Status>
    <Get>
      <CmdID>2</CmdID>
      <Item>
        <Target><LocURI>./DevInfo/Mod</LocURI></Target>
      </Item>
      <Item>
        <Target><LocURI>./Software/Build</LocURI></Target>
      </Item>
    </Get>
    <Final/>
  </SyncBody>
</SyncML>
```

## WBXML Token Tables

SyncML 1.2 uses these WBXML public identifiers:
- SyncML: `-//SYNCML//DTD SyncML 1.2//EN` (0x1201)
- MetInf: `-//SYNCML//DTD MetInf 1.2//EN`
- DevInf: `-//SYNCML//DTD DevInf 1.2//EN`

Key tokens (tag page 0x00):
```python
SYNCML_TOKENS = {
    0x05: 'Add',
    0x06: 'Alert',
    0x07: 'Archive',
    0x08: 'Atomic',
    0x09: 'Chal',
    0x0A: 'Cmd',
    0x0B: 'CmdID',
    0x0C: 'CmdRef',
    0x0D: 'Copy',
    0x0E: 'Cred',
    0x0F: 'Data',
    0x10: 'Delete',
    0x11: 'Exec',
    0x12: 'Final',
    0x13: 'Get',
    0x14: 'Item',
    0x15: 'Lang',
    0x16: 'LocName',
    0x17: 'LocURI',
    0x18: 'Map',
    # ... etc
}
```

## Implementation Steps

### Phase 1: Core Infrastructure
1. Set up FastAPI project structure
2. Implement WBXML decoder (parse device messages)
3. Implement WBXML encoder (build server responses)
4. Add basic logging and request capture

### Phase 2: SyncML Protocol
5. Implement SyncML message parser
6. Implement SyncML response builder
7. Add HMAC-MD5 authentication
8. Implement session state management

### Phase 3: OMA DM Logic
9. Implement DM tree operations (GET/REPLACE/ADD)
10. Add update availability logic
11. Configure package URLs and metadata
12. Handle EXEC for DownloadAndInstall

### Phase 4: Package Hosting
13. Implement package download endpoint
14. Add range request support (resumable downloads)
15. Generate package manifest

### Phase 5: Device Integration
16. Create modified DmTree.xml for device
17. Document device deployment process
18. Test full update flow on TouchPad

### Phase 6: Polish
19. Add web UI for server management
20. Improve error handling
21. Add comprehensive logging
22. Write documentation

## Device Deployment

To redirect TouchPad to local server:

1. Enable developer mode on device
2. Connect via USB/novacom or SSH
3. Remount root filesystem read-write:
   ```bash
   mount -o remount,rw /
   ```
4. Edit `/usr/share/omadm/DmTree.xml`:
   - Change server URL from `https://ps.palmws.com/palmcsext/swupdateserver`
   - To `http://<your-server-ip>:8080/palmcsext/swupdateserver`
5. Optionally add server's CA cert if using HTTPS
6. Reboot device

## Key Source Files Reference

From extracted webOS rootfs:
- `rootfs/usr/share/omadm/DmTree.xml` - DM tree config template
- `rootfs/usr/bin/OmaDm` - Binary for protocol analysis
- `rootfs/usr/bin/UpdateDaemon` - Update orchestration
- `rootfs/usr/share/ota-scripts/` - Installation scripts
- `rootfs/var/lib/software/SessionFiles/` - Runtime state files

## Testing Approach

1. **Unit Tests**: WBXML codec, SyncML parser/builder
2. **Integration Tests**: Full session simulation with captured device traffic
3. **Device Tests**:
   - Trigger manual update check
   - Verify server receives valid SyncML
   - Confirm device downloads package
   - Test actual update installation (use safe test package first)

---

## Current Status (2025-12-31)

### Completed

- **Phase 1: Core Infrastructure** - COMPLETE
  - FastAPI server running on port 8080
  - WBXML decoder/encoder implemented
  - Request logging and capture working

- **Phase 2: SyncML Protocol** - PARTIAL
  - SyncML message parser working (with namespace stripping fix)
  - SyncML response builder working
  - Session state management implemented
  - HMAC-MD5 authentication: **NOT YET WORKING**

- **Phase 3: OMA DM Logic** - PARTIAL
  - DM tree GET/REPLACE operations implemented
  - Update availability logic implemented
  - Package URL and metadata configured
  - EXEC for DownloadAndInstall implemented

- **Phase 4: Package Hosting** - COMPLETE
  - Package download endpoint working
  - Range request support for resumable downloads
  - Package manifest generation

- **Phase 5: Device Integration** - PARTIAL
  - Modified DmTree.xml created
  - Deploy script fixed (novacom syntax)
  - Device successfully connects to server
  - **Authentication failing (407/401 status)**

### Key Discovery: Multiple DmTree.xml Locations

The device has THREE locations where DmTree.xml exists:

| File | Purpose | Writeable |
|------|---------|-----------|
| `/usr/share/omadm/DmTree.xml` | Source/template | No (read-only /) |
| `/var/lib/software/DmTree.xml` | Runtime config (used by OmaDm) | Yes |
| `/var/lib/software/DmTree.backup.xml` | Backup (OmaDm regenerates from this) | Yes |

**Important**: OmaDm reads from `/var/lib/software/DmTree.xml` at runtime, NOT from `/usr/share/omadm/DmTree.xml`. If only the `/usr/share/` version is modified, OmaDm will still use the old Palm URL.

### Fixes Applied

1. **deploy.sh novacom syntax** - Changed from broken `novacom run -- "cmd"` to working `echo "cmd" | novacom run file://bin/sh`

2. **SyncML parser namespace handling** - Added `_strip_namespaces()` method to handle `xmlns='SYNCML:SYNCML1.2'` namespace in XML

3. **config.py missing constants** - Added `SESSION_TIMEOUT`, `SERVER_HOST`, `SERVER_PORT`, and flat `STATUS_*`/`ALERT_*` constants

---

## Next Steps

### Immediate Priority: Fix HMAC-MD5 Authentication

The device is connecting but rejecting the server's response with status codes:
- **407** for SyncHdr (authentication rejected)
- **401** for commands (unauthorized)

The server must properly implement HMAC-MD5 authentication:

1. **Parse incoming HMAC header** from device request:
   ```
   x-syncml-hmac: algorithm=MD5, username=guest, mac=<base64-digest>
   ```

2. **Verify device's HMAC** using:
   - Algorithm: HMAC-MD5
   - Key: `guestpassword` (hardcoded guest password)
   - Data: Message body (WBXML bytes)

3. **Generate server HMAC** for response:
   - Include `x-syncml-hmac` header in response
   - Use device's nonce if provided, or generate new one

4. **Return proper status code**:
   - 212 = Authentication accepted
   - 401 = Unauthorized (wrong credentials)
   - 407 = Authentication required

### Files to Modify

- `syncml/auth.py` - Implement proper HMAC verification and generation
- `server.py` - Integrate authentication into request/response flow

### Testing Authentication

1. Start server: `python server.py`
2. On device, update all DmTree files:
   ```bash
   # Via novacom
   echo "sed -i 's|https://ps.palmws.com|http://192.168.10.20:8080|g' /var/lib/software/DmTree.xml" | novacom run file://bin/sh
   echo "sed -i 's|https://ps.palmws.com|http://192.168.10.20:8080|g' /var/lib/software/DmTree.backup.xml" | novacom run file://bin/sh
   ```
3. Run OmaDm manually: `echo '/usr/bin/OmaDm' | novacom run file://bin/sh`
4. Check server logs for HMAC header and verify authentication flow

### After Authentication Works

- Test full update flow with a safe test package
- Verify device downloads package from server
- Test actual update installation
