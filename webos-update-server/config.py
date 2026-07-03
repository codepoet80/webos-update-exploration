"""
Configuration for webOS Update Server
"""
import os
import socket
import configparser
from pathlib import Path

BASE_DIR = Path(__file__).parent


def _lan_ip():
    """Best-effort primary LAN IP of this host (the address devices reach us on).
    Uses a UDP socket toward the LAN gateway range — no packets are actually sent."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.168.10.1", 1))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


# --- Settings come from a config file (not environment variables). ---
# Searched in order; first found wins; missing file -> built-in defaults:
#   /etc/otaserver.conf      (production)
#   <repo>/otaserver.conf    (local/dev; shipped with dev defaults)
# interpolation=None so URLs containing '%' are not mangled.
_conf = configparser.ConfigParser(interpolation=None)
CONF_PATH = None
for _p in ("/etc/otaserver.conf", str(BASE_DIR / "otaserver.conf")):
    if os.path.exists(_p):
        _conf.read(_p)
        CONF_PATH = _p
        break


def _cget(section, key, default=""):
    return (_conf.get(section, key, fallback=default) or "").strip()


# Server settings
HOST = _cget("server", "host", "0.0.0.0") or "0.0.0.0"
PORT = int(_cget("server", "port", "8080") or "8080")
DEBUG = _cget("server", "debug", "true").lower() in ("1", "true", "yes", "on")
SESSION_TIMEOUT = int(_cget("server", "session_timeout", "3600") or "3600")

# Aliases for server.py compatibility
SERVER_HOST = HOST
SERVER_PORT = PORT

# Paths
PACKAGES_DIR = BASE_DIR / "packages"
CERTS_DIR = BASE_DIR / "certs"

# Server identity
SERVER_ID = "webos-update-server"

# Base URL for package downloads (used in API responses).
#   [public] url set   -> used verbatim (full control)
#   [public] host set  -> https://<host>            (production deploy)
#   neither            -> http://<LAN IP>:<PORT>    (local dev, auto-detected)
# Palm's original OTA host was omadm.swupdate.palm.com; we match the "swupdate"
# label on our own domain for the community server.
PUBLIC_HOST = _cget("public", "host", "")
_server_url = _cget("public", "url", "")
if _server_url:
    SERVER_URL = _server_url
elif PUBLIC_HOST:
    SERVER_URL = f"https://{PUBLIC_HOST}"
else:
    SERVER_URL = f"http://{_lan_ip()}:{PORT}"

# Optional persistent rotating access log; blank -> stdout/journald only.
LOG_FILE = _cget("logging", "file", "") or None
# Legacy OMA DM endpoint path (kept for reference)
DM_ENDPOINT = "/palmcsext/swupdateserver"

# Default credentials (from device DmTree.xml)
# Client authenticates as guest
DEFAULT_USERNAME = "guest"
DEFAULT_PASSWORD = "guestpassword"
# Server authenticates as webos-update-server (must match DmTree.xml AAuthName/AAuthSecret)
SERVER_USERNAME = "webos-update-server"
SERVER_PASSWORD = "serverpassword"

# Update configuration
UPDATE_VERSION = "3.0.6"  # Version to offer
UPDATE_BUILD = "1000"     # Build number to offer

# SyncML Status Codes
class StatusCode:
    SUCCESS = 200
    ITEM_ADDED = 201
    ACCEPTED_FOR_PROCESSING = 202
    NON_AUTHORITATIVE = 203
    NO_CONTENT = 204
    RESET_CONTENT = 205
    PARTIAL_CONTENT = 206
    CONFLICT = 208
    GONE = 210
    AUTH_ACCEPTED = 212
    CHUNKED_ITEM_ACCEPTED = 213
    OPERATION_CANCELLED = 214
    NOT_EXECUTED = 215
    ATOMIC_ROLLBACK_OK = 216

    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    COMMAND_NOT_ALLOWED = 405
    OPTIONAL_FEATURE_NOT_SUPPORTED = 406
    MISSING_CREDENTIALS = 407
    REQUEST_TIMEOUT = 408
    INCOMPLETE_COMMAND = 412
    REQUEST_ENTITY_TOO_LARGE = 413
    URI_TOO_LONG = 414
    UNSUPPORTED_MEDIA_TYPE = 415
    REQUEST_SIZE_TOO_BIG = 416
    RETRY_LATER = 417
    ALREADY_EXISTS = 418
    CONFLICT_RESOLVED_WITH_MERGE = 419
    DEVICE_FULL = 420
    UNKNOWN_SEARCH_GRAMMAR = 421
    BAD_CGI = 422
    SOFT_DELETE_CONFLICT = 423
    SIZE_MISMATCH = 424
    PERMISSION_DENIED = 425
    PARTIAL_ITEM_NOT_ACCEPTED = 426
    ITEM_NOT_EMPTY = 427
    MOVE_FAILED = 428

    COMMAND_FAILED = 500
    NOT_IMPLEMENTED = 501
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503
    GATEWAY_TIMEOUT = 504
    PROCESSING_ERROR = 506
    ATOMIC_FAILED = 507
    REFRESH_REQUIRED = 508
    DATA_STORE_FAILURE = 510
    SERVER_FAILURE = 511
    SYNC_FAILED = 512
    PROTOCOL_VERSION_NOT_SUPPORTED = 513
    OPERATION_CANCELLED_BY_USER = 514
    ATOMIC_ROLLBACK_FAILED = 516
    ATOMIC_RESPONSE_TOO_LARGE = 517

# OMA DM Alert Codes
class AlertCode:
    DISPLAY = 1100
    CONFIRM_OR_REJECT = 1101
    TEXT_INPUT = 1102
    SINGLE_CHOICE = 1103
    MULTIPLE_CHOICE = 1104
    CLIENT_INITIATED_MGMT = 1201
    NEXT_MESSAGE = 1222
    SESSION_ABORT = 1223
    CLIENT_EVENT = 1224
    NO_END_OF_DATA = 1225
    GENERIC_ALERT = 1226

# Flat constants for server.py compatibility
STATUS_OK = StatusCode.SUCCESS
STATUS_AUTH_ACCEPTED = StatusCode.AUTH_ACCEPTED
STATUS_CREDENTIALS_MISSING = StatusCode.MISSING_CREDENTIALS
STATUS_ACCEPTED_FOR_PROCESSING = StatusCode.ACCEPTED_FOR_PROCESSING

ALERT_CLIENT_INITIATED = AlertCode.CLIENT_INITIATED_MGMT
ALERT_SERVER_INITIATED = 1200  # Server-initiated session
ALERT_DISPLAY = AlertCode.DISPLAY
ALERT_CONFIRM = AlertCode.CONFIRM_OR_REJECT
ALERT_USER_INPUT = AlertCode.TEXT_INPUT
