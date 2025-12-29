"""
SyncML Session Management

Manages OMA DM sessions between server and devices.
"""
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any
from enum import Enum


class SessionState(Enum):
    """Session state machine states"""
    INIT = "init"
    AUTHENTICATED = "authenticated"
    MANAGEMENT = "management"
    UPDATE_AVAILABLE = "update_available"
    DOWNLOADING = "downloading"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class DeviceInfo:
    """Device information collected during session"""
    device_id: str = ""
    manufacturer: str = ""
    model: str = ""
    firmware_version: str = ""
    software_version: str = ""
    hardware_version: str = ""
    current_build: str = ""
    dm_version: str = ""
    language: str = ""


@dataclass
class Session:
    """OMA DM Session"""
    session_id: str
    device_id: str
    state: SessionState = SessionState.INIT
    msg_id: int = 0
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    device_info: DeviceInfo = field(default_factory=DeviceInfo)
    authenticated: bool = False
    username: str = ""
    client_nonce: bytes = b""
    server_nonce: bytes = b""
    pending_commands: List[Any] = field(default_factory=list)
    command_results: Dict[str, Any] = field(default_factory=dict)

    def next_msg_id(self) -> str:
        """Get next message ID"""
        self.msg_id += 1
        self.last_activity = time.time()
        return str(self.msg_id)

    def is_expired(self, timeout: int = 3600) -> bool:
        """Check if session has expired"""
        return time.time() - self.last_activity > timeout

    def update_device_info(self, path: str, value: str):
        """Update device info from DM tree path"""
        path_lower = path.lower()

        if 'devid' in path_lower:
            self.device_info.device_id = value
        elif 'man' in path_lower and 'command' not in path_lower:
            self.device_info.manufacturer = value
        elif 'mod' in path_lower:
            self.device_info.model = value
        elif 'fwv' in path_lower or 'fmv' in path_lower:
            self.device_info.firmware_version = value
        elif 'swv' in path_lower:
            self.device_info.software_version = value
        elif 'hwv' in path_lower:
            self.device_info.hardware_version = value
        elif 'build' in path_lower:
            self.device_info.current_build = value
        elif 'dmv' in path_lower:
            self.device_info.dm_version = value
        elif 'lang' in path_lower:
            self.device_info.language = value


class SessionManager:
    """Manage active OMA DM sessions"""

    def __init__(self, session_timeout: int = 3600):
        self.sessions: Dict[str, Session] = {}
        self.session_timeout = session_timeout
        self._session_counter = 0

    def create_session(self, device_id: str, session_id: str = None) -> Session:
        """Create a new session"""
        if session_id is None:
            self._session_counter += 1
            session_id = str(self._session_counter)

        session = Session(
            session_id=session_id,
            device_id=device_id
        )

        # Generate server nonce
        import os
        session.server_nonce = os.urandom(16)

        self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID"""
        session = self.sessions.get(session_id)
        if session and not session.is_expired(self.session_timeout):
            return session
        return None

    def get_or_create_session(self, device_id: str, session_id: str) -> Session:
        """Get existing session or create new one"""
        session = self.get_session(session_id)
        if session:
            return session
        return self.create_session(device_id, session_id)

    def remove_session(self, session_id: str):
        """Remove a session"""
        if session_id in self.sessions:
            del self.sessions[session_id]

    def cleanup_expired(self):
        """Remove expired sessions"""
        expired = [
            sid for sid, session in self.sessions.items()
            if session.is_expired(self.session_timeout)
        ]
        for sid in expired:
            del self.sessions[sid]

    def get_session_by_device(self, device_id: str) -> Optional[Session]:
        """Get active session for a device"""
        for session in self.sessions.values():
            if session.device_id == device_id and not session.is_expired(self.session_timeout):
                return session
        return None
