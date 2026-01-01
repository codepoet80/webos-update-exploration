"""
webOS Update Server

A local OMA DM server replacement for HP TouchPad devices.
Implements the SyncML/OMA DM protocol for software updates.
"""
import logging
import base64
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

import config
from wbxml import WBXMLDecoder, WBXMLEncoder
from syncml import SyncMLParser, SyncMLBuilder, HMACAuth, SessionManager, Session
from syncml.builder import StatusBuilder, ItemBuilder
from syncml.parser import SyncMLMessage
from dm import DMTree, UpdateManager

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="webOS Update Server",
    description="OMA DM server for HP TouchPad software updates",
    version="1.0.0"
)

# Initialize components
session_manager = SessionManager(session_timeout=config.SESSION_TIMEOUT)
update_manager = UpdateManager(config.PACKAGES_DIR)
auth_handler = HMACAuth()


def get_client_ip(request: Request) -> str:
    """Get client IP address from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.on_event("startup")
async def startup_event():
    """Initialize server on startup"""
    logger.info(f"webOS Update Server starting on {config.SERVER_HOST}:{config.SERVER_PORT}")
    logger.info(f"Server ID: {config.SERVER_ID}")
    logger.info(f"Packages directory: {config.PACKAGES_DIR}")

    # Scan for packages
    update_manager.scan_packages()
    logger.info(f"Found {len(update_manager.packages)} update packages")


@app.get("/")
async def root():
    """Server info endpoint"""
    return {
        "name": "webOS Update Server",
        "version": "1.0.0",
        "status": "running",
        "server_id": config.SERVER_ID,
        "packages": len(update_manager.packages),
    }


@app.get("/status")
async def status():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "sessions": len(session_manager.sessions),
        "packages": len(update_manager.packages),
    }


@app.post("/palmcsext/swupdateserver")
async def oma_dm_endpoint(request: Request):
    """
    Main OMA DM SyncML endpoint.

    Handles all device management communication.
    """
    client_ip = get_client_ip(request)
    content_type = request.headers.get("Content-Type", "")

    # Read request body
    body = await request.body()

    logger.info(f"OMA DM request from {client_ip}, Content-Type: {content_type}, Size: {len(body)} bytes")

    # Check for HMAC authentication header
    hmac_header = request.headers.get("x-syncml-hmac", "")
    client_nonce = b""  # Default empty nonce for first exchange

    if hmac_header:
        logger.debug(f"HMAC header: {hmac_header}")
        # Parse the HMAC header to extract any nonce
        auth_parser = HMACAuth()
        hmac_parts = auth_parser.parse_hmac_header(hmac_header)
        logger.debug(f"HMAC parts: {hmac_parts}")

    try:
        # Parse the SyncML message
        parser = SyncMLParser()
        message = parser.parse(body, content_type)

        logger.info(f"Session: {message.header.session_id}, MsgID: {message.header.msg_id}")
        logger.info(f"Source: {message.header.source}, Target: {message.header.target}")
        logger.debug(f"Commands: {[c.name for c in message.commands]}")

        # Get or create session
        session = session_manager.get_or_create_session(
            device_id=message.header.source,
            session_id=message.header.session_id
        )

        # Extract client nonce from message meta if present
        if message.header.meta.get('NextNonce'):
            try:
                client_nonce = base64.b64decode(message.header.meta['NextNonce'])
                session.client_nonce = client_nonce
                logger.debug(f"Got client NextNonce: {client_nonce.hex()}")
            except Exception as e:
                logger.warning(f"Failed to decode client nonce: {e}")

        # Handle authentication
        if not session.authenticated:
            # Verify client's HMAC if provided
            if hmac_header:
                auth = HMACAuth()
                hmac_parts = auth.parse_hmac_header(hmac_header)
                client_mac = hmac_parts.get('mac', '')
                client_username = hmac_parts.get('username', config.DEFAULT_USERNAME)

                # Use server's nonce for verification (empty for first message)
                verify_nonce = session.server_nonce if session.server_nonce else b""
                expected_mac = auth.compute_hmac(
                    client_username,
                    config.DEFAULT_PASSWORD,
                    verify_nonce,
                    body
                )

                if client_mac == expected_mac:
                    logger.info(f"Client HMAC verified successfully")
                    session.authenticated = True
                else:
                    logger.warning(f"Client HMAC mismatch. Got: {client_mac}, Expected: {expected_mac}")
                    # Accept anyway for now to debug further
                    session.authenticated = True
            else:
                # No HMAC - accept for testing
                session.authenticated = True

            session.username = message.header.cred_data or "guest"
            logger.info(f"Session {session.session_id} authenticated as {session.username}")

        # Process the message and build response
        response_xml = process_dm_message(session, message, body)

        # Encode response
        builder = SyncMLBuilder()

        if 'wbxml' in content_type:
            # Return WBXML
            response_body = builder.to_wbxml(response_xml)
            response_content_type = "application/vnd.syncml.dm+wbxml"
        else:
            # Return XML
            response_body = builder.to_xml_string(response_xml).encode('utf-8')
            response_content_type = "application/vnd.syncml.dm+xml"

        logger.info(f"Response size: {len(response_body)} bytes")

        # Build response with HMAC if client sent HMAC
        response_headers = {}
        if hmac_header:
            auth = HMACAuth()
            # Use client's nonce if available, otherwise empty
            nonce_for_response = session.client_nonce if session.client_nonce else b""
            mac = auth.compute_hmac(
                config.SERVER_USERNAME,
                config.SERVER_PASSWORD,
                nonce_for_response,
                response_body
            )
            response_headers["x-syncml-hmac"] = (
                f"algorithm=MD5, username={config.SERVER_USERNAME}, mac={mac}"
            )
            logger.debug(f"Response HMAC: algorithm=MD5, username={config.SERVER_USERNAME}, mac={mac}")
            logger.debug(f"Response nonce used: {nonce_for_response.hex() if nonce_for_response else '(empty)'}")

        return Response(
            content=response_body,
            media_type=response_content_type,
            headers=response_headers
        )

    except Exception as e:
        logger.exception(f"Error processing OMA DM request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def process_dm_message(session: Session, message: SyncMLMessage, raw_body: bytes):
    """
    Process incoming SyncML message and build response.

    Implements the OMA DM server state machine.
    """
    builder = SyncMLBuilder()
    statuses = []
    commands = []

    msg_ref = message.header.msg_id
    next_msg_id = session.next_msg_id()

    # Status for SyncHdr (command reference 0)
    statuses.append(StatusBuilder(
        cmd_id="",  # Will be set by builder
        msg_ref=msg_ref,
        cmd_ref="0",
        cmd="SyncHdr",
        data=config.STATUS_AUTH_ACCEPTED if session.authenticated else config.STATUS_CREDENTIALS_MISSING,
        target_ref=message.header.target,
        source_ref=message.header.source,
    ))

    # Process each command in the message
    for cmd in message.commands:
        logger.debug(f"Processing command: {cmd.name} (CmdID: {cmd.cmd_id})")

        if cmd.name == "Alert":
            status, new_commands = handle_alert(session, cmd, message, builder)
            statuses.append(status)
            commands.extend(new_commands)

        elif cmd.name == "Status":
            handle_status(session, cmd)
            # Status commands don't need a response status

        elif cmd.name == "Results":
            status = handle_results(session, cmd, message)
            statuses.append(status)

        elif cmd.name == "Replace":
            status = handle_replace(session, cmd, message)
            statuses.append(status)

        elif cmd.name == "Get":
            status, results = handle_get(session, cmd, message, builder)
            statuses.append(status)
            if results:
                commands.append(results)

        else:
            # Unknown command - acknowledge with OK
            statuses.append(StatusBuilder(
                cmd_id="",
                msg_ref=msg_ref,
                cmd_ref=cmd.cmd_id,
                cmd=cmd.name,
                data=config.STATUS_OK,
            ))

    # Check if we need to send update info
    if session.state.value in ["authenticated", "management"]:
        update_commands = check_and_send_update(session, builder)
        commands.extend(update_commands)

    # Build response message
    response = builder.build_response(
        session_id=session.session_id,
        msg_id=next_msg_id,
        target=message.header.source,
        source=config.SERVER_ID,
        statuses=statuses,
        commands=commands,
        is_final=True
    )

    return response


def handle_alert(session: Session, cmd, message: SyncMLMessage, builder: SyncMLBuilder):
    """Handle Alert command"""
    alert_code = int(cmd.data) if cmd.data else 0
    logger.info(f"Alert code: {alert_code}")

    status = StatusBuilder(
        cmd_id="",
        msg_ref=message.header.msg_id,
        cmd_ref=cmd.cmd_id,
        cmd="Alert",
        data=config.STATUS_OK,
    )

    commands = []

    if alert_code == config.ALERT_CLIENT_INITIATED:
        # Client-initiated session (1201)
        # Request device info
        logger.info("Client-initiated session, requesting device info")
        from syncml.session import SessionState
        session.state = SessionState.AUTHENTICATED

        # Get device information
        get_cmd = builder.build_get([
            "./DevInfo/DevId",
            "./DevInfo/Man",
            "./DevInfo/Mod",
            "./DevInfo/FwV",
            "./DevInfo/SwV",
            "./DevInfo/HwV",
            "./Software/Build",
        ])
        commands.append(get_cmd)

    elif alert_code == config.ALERT_SERVER_INITIATED:
        # Server-initiated session (1200)
        logger.info("Server-initiated session")

    elif alert_code == config.ALERT_DISPLAY:
        # Display alert (1100) - user notification
        logger.info("Display alert from device")

    elif alert_code == config.ALERT_CONFIRM:
        # Confirmation alert (1101)
        logger.info("Confirmation alert from device")

    elif alert_code == config.ALERT_USER_INPUT:
        # User input alert (1102)
        logger.info("User input alert from device")

    return status, commands


def handle_status(session: Session, cmd):
    """Handle Status command from device"""
    status_code = int(cmd.data) if cmd.data else 0
    target_ref = cmd.target_ref or ""

    logger.debug(f"Status for {cmd.cmd} (ref {cmd.cmd_ref}): {status_code} - {target_ref}")

    # Store status for tracking
    key = f"{cmd.cmd_ref}_{target_ref}"
    session.command_results[key] = {
        "cmd": cmd.cmd,
        "status": status_code,
        "target": target_ref,
    }

    # Check for download completion
    if "DownloadAndInstall" in target_ref or "Download" in target_ref:
        if status_code == config.STATUS_OK:
            logger.info("Device acknowledged download command")
        elif status_code == config.STATUS_ACCEPTED_FOR_PROCESSING:
            logger.info("Device accepted download for processing")


def handle_results(session: Session, cmd, message: SyncMLMessage):
    """Handle Results command (response to Get)"""
    for item in cmd.items:
        source = item.source or ""
        data = item.data or ""

        logger.info(f"Result: {source} = {data}")

        # Update session device info
        session.update_device_info(source, data)

    from syncml.session import SessionState
    if session.state == SessionState.AUTHENTICATED:
        session.state = SessionState.MANAGEMENT

    return StatusBuilder(
        cmd_id="",
        msg_ref=message.header.msg_id,
        cmd_ref=cmd.cmd_id,
        cmd="Results",
        data=config.STATUS_OK,
    )


def handle_replace(session: Session, cmd, message: SyncMLMessage):
    """Handle Replace command from device"""
    for item in cmd.items:
        target = item.target or ""
        data = item.data or ""
        logger.info(f"Replace: {target} = {data}")

    return StatusBuilder(
        cmd_id="",
        msg_ref=message.header.msg_id,
        cmd_ref=cmd.cmd_id,
        cmd="Replace",
        data=config.STATUS_OK,
    )


def handle_get(session: Session, cmd, message: SyncMLMessage, builder: SyncMLBuilder):
    """Handle Get command from device"""
    results_items = []

    for item in cmd.items:
        target = item.target or ""
        logger.info(f"Get request for: {target}")

        # Return requested values from our tree
        value = None
        if "Build" in target:
            value = session.device_info.current_build or "Nova-3.0.5-64"
        elif "PkgURL" in target:
            pkg = update_manager.check_update_available(
                session.device_info.current_build
            )
            if pkg:
                value = update_manager.get_package_url(pkg)

        if value:
            results_items.append(ItemBuilder(
                source=target,
                data=value,
            ))

    status = StatusBuilder(
        cmd_id="",
        msg_ref=message.header.msg_id,
        cmd_ref=cmd.cmd_id,
        cmd="Get",
        data=config.STATUS_OK,
    )

    results = None
    if results_items:
        results = builder.build_results(
            msg_ref=message.header.msg_id,
            cmd_ref=cmd.cmd_id,
            items=results_items
        )

    return status, results


def check_and_send_update(session: Session, builder: SyncMLBuilder):
    """Check if update is available and send update commands"""
    commands = []

    # Check for available update
    device_build = session.device_info.current_build or session.device_info.software_version
    if not device_build:
        logger.debug("No device build info yet, skipping update check")
        return commands

    logger.info(f"Checking updates for device build: {device_build}")

    pkg = update_manager.check_update_available(device_build)
    if not pkg:
        logger.info("No update available for device")
        return commands

    logger.info(f"Update available: {pkg.name} ({pkg.version})")

    from syncml.session import SessionState
    session.state = SessionState.UPDATE_AVAILABLE

    # Send update package info via Replace commands
    pkg_url = update_manager.get_package_url(pkg)

    replace_items = [
        ItemBuilder(target="./Software/Package/PkgName", data=pkg.name),
        ItemBuilder(target="./Software/Package/PkgVersion", data=pkg.version),
        ItemBuilder(target="./Software/Package/PkgURL", data=pkg_url),
        ItemBuilder(target="./Software/Package/PkgSize", data=str(pkg.size)),
        ItemBuilder(target="./Software/Package/PkgDesc", data=pkg.description),
    ]

    if pkg.install_notify_url:
        replace_items.append(
            ItemBuilder(target="./Software/Package/PkgInstallNotify", data=pkg.install_notify_url)
        )

    commands.append(builder.build_replace(replace_items))

    # Send Exec command to trigger download
    commands.append(builder.build_exec("./Software/Operations/DownloadAndInstall"))

    return commands


# Package hosting endpoints

@app.get("/packages/manifest.json")
async def get_manifest():
    """Get package manifest"""
    return JSONResponse(update_manager.get_manifest())


@app.get("/packages/{filename}")
async def download_package(filename: str, request: Request):
    """
    Download update package.

    Supports range requests for resumable downloads.
    """
    path = update_manager.get_package_path(filename)
    if not path:
        raise HTTPException(status_code=404, detail="Package not found")

    file_size = path.stat().st_size

    # Check for range request
    range_header = request.headers.get("Range")
    if range_header:
        # Parse range header: bytes=start-end
        try:
            range_spec = range_header.replace("bytes=", "")
            start, end = range_spec.split("-")
            start = int(start) if start else 0
            end = int(end) if end else file_size - 1

            if start >= file_size:
                raise HTTPException(status_code=416, detail="Range not satisfiable")

            end = min(end, file_size - 1)
            length = end - start + 1

            # Read the requested range
            with open(path, "rb") as f:
                f.seek(start)
                content = f.read(length)

            return Response(
                content=content,
                status_code=206,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Content-Length": str(length),
                    "Accept-Ranges": "bytes",
                },
                media_type="application/octet-stream"
            )
        except ValueError:
            pass  # Fall through to full file download

    # Full file download
    return FileResponse(
        path=path,
        filename=filename,
        media_type="application/octet-stream",
        headers={"Accept-Ranges": "bytes"}
    )


@app.post("/packages/scan")
async def scan_packages():
    """Rescan packages directory"""
    update_manager.scan_packages()
    return {"status": "ok", "packages": len(update_manager.packages)}


@app.get("/sessions")
async def list_sessions():
    """List active sessions (debug endpoint)"""
    return {
        "sessions": [
            {
                "session_id": s.session_id,
                "device_id": s.device_id,
                "state": s.state.value,
                "authenticated": s.authenticated,
                "device_info": {
                    "model": s.device_info.model,
                    "manufacturer": s.device_info.manufacturer,
                    "build": s.device_info.current_build,
                    "firmware": s.device_info.firmware_version,
                },
                "msg_id": s.msg_id,
            }
            for s in session_manager.sessions.values()
        ]
    }


# Direct Update API - bypasses OMA DM for WiFi-only devices

@app.get("/api/updates/check")
async def check_updates_direct(build: str = "", swv: str = ""):
    """
    Direct update check endpoint - bypasses OMA DM.

    Parameters:
    - build: Current device build (e.g., "Nova-3.0.5-86")
    - swv: Software version (e.g., "3.0.5")

    Returns available updates in a simple JSON format.
    Returns all packages in the update bundle.
    """
    device_build = build or swv

    if not device_build:
        return JSONResponse({
            "status": "error",
            "message": "Missing build or swv parameter",
            "updateAvailable": False
        })

    logger.info(f"Direct update check for build: {device_build}")

    # Get all packages that apply to this device build
    all_packages = []
    for pkg in update_manager.packages.values():
        # Check if this package applies to the device
        if pkg.target_build:
            pkg_target = update_manager._parse_build_version(pkg.target_build)
            device_ver = update_manager._parse_build_version(device_build)
            if device_ver >= pkg_target:
                continue  # Already at or past this version

        pkg_url = update_manager.get_package_url(pkg)
        all_packages.append({
            "name": pkg.name,
            "version": pkg.version,
            "filename": pkg.filename,
            "url": pkg_url,
            "size": pkg.size,
            "md5": pkg.md5,
            "description": pkg.description,
            "targetBuild": pkg.target_build
        })

    if not all_packages:
        return JSONResponse({
            "status": "ok",
            "updateAvailable": False,
            "currentBuild": device_build
        })

    return JSONResponse({
        "status": "ok",
        "updateAvailable": True,
        "currentBuild": device_build,
        "packageCount": len(all_packages),
        "packages": all_packages
    })


@app.get("/api/updates/urls")
async def get_update_urls(build: str = ""):
    """
    Get update URLs in the format expected by UpdateDaemon.

    Returns URLs file content that can be written to
    /var/lib/software/SessionFiles/urls
    """
    if not build:
        return Response(content="", media_type="text/plain")

    pkg = update_manager.check_update_available(build)

    if not pkg:
        return Response(content="", media_type="text/plain")

    pkg_url = update_manager.get_package_url(pkg)

    # Format: one URL per line
    urls_content = f"{pkg_url}\n"

    return Response(content=urls_content, media_type="text/plain")


@app.get("/api/updates/session-files")
async def get_session_files(build: str = ""):
    """
    Get all session files needed for update in a single response.

    Returns a JSON object containing:
    - urls: Download URLs
    - update_list: Package list
    - Other metadata
    """
    if not build:
        return JSONResponse({
            "status": "error",
            "message": "Missing build parameter"
        })

    pkg = update_manager.check_update_available(build)

    if not pkg:
        return JSONResponse({
            "status": "ok",
            "updateAvailable": False
        })

    pkg_url = update_manager.get_package_url(pkg)
    pkg_path = f"/var/lib/update/{pkg.filename}"

    return JSONResponse({
        "status": "ok",
        "updateAvailable": True,
        "files": {
            "urls": pkg_url,
            "update_list": pkg_path,
            "package": {
                "name": pkg.name,
                "version": pkg.version,
                "size": pkg.size,
                "md5": pkg.md5
            }
        }
    })


def run_server():
    """Run the server"""
    uvicorn.run(
        "server:app",
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        reload=config.DEBUG,
        log_level="debug" if config.DEBUG else "info",
    )


if __name__ == "__main__":
    run_server()
