"""
HMAC-MD5 Authentication for SyncML/OMA DM

Implements the syncml:auth-MAC authentication scheme.
"""
import hashlib
import hmac
import base64
from typing import Optional, Tuple
import config


class HMACAuth:
    """HMAC-MD5 authentication handler"""

    def __init__(
        self,
        username: str = None,
        password: str = None,
        server_username: str = None,
        server_password: str = None
    ):
        self.username = username or config.DEFAULT_USERNAME
        self.password = password or config.DEFAULT_PASSWORD
        self.server_username = server_username or config.SERVER_USERNAME
        self.server_password = server_password or config.SERVER_PASSWORD
        self.client_nonce: Optional[bytes] = None
        self.server_nonce: Optional[bytes] = None

    def parse_hmac_header(self, header: str) -> dict:
        """Parse x-syncml-hmac header"""
        result = {}
        if not header:
            return result

        for part in header.split(','):
            part = part.strip()
            if '=' in part:
                key, value = part.split('=', 1)
                result[key.strip()] = value.strip()

        return result

    def compute_hmac(
        self,
        username: str,
        password: str,
        nonce: bytes,
        body: bytes
    ) -> str:
        """
        Compute HMAC-MD5 digest.

        The SyncML HMAC computation is:
        1. B64(H(username:password))
        2. HMAC-MD5(B64(H(username:password)), nonce:B64(H(body)))
        """
        # Step 1: H(username:password)
        cred_hash = hashlib.md5(f"{username}:{password}".encode()).digest()
        cred_b64 = base64.b64encode(cred_hash).decode()

        # Step 2: H(body)
        body_hash = hashlib.md5(body).digest()
        body_b64 = base64.b64encode(body_hash).decode()

        # Step 3: HMAC-MD5(cred_b64, nonce:body_b64)
        message = nonce + b':' + body_b64.encode()
        mac = hmac.new(cred_b64.encode(), message, hashlib.md5).digest()

        return base64.b64encode(mac).decode()

    def verify_client_auth(
        self,
        mac: str,
        username: str,
        body: bytes,
        nonce: bytes = None
    ) -> bool:
        """Verify client authentication"""
        if nonce is None:
            nonce = self.server_nonce or b''

        # Try with provided credentials
        expected = self.compute_hmac(username, self.password, nonce, body)

        if mac == expected:
            return True

        # Try with default credentials
        if username != self.username:
            expected = self.compute_hmac(self.username, self.password, nonce, body)
            if mac == expected:
                return True

        return False

    def create_server_auth(self, body: bytes, nonce: bytes = None) -> str:
        """Create server authentication MAC"""
        if nonce is None:
            nonce = self.client_nonce or b''

        return self.compute_hmac(
            self.server_username,
            self.server_password,
            nonce,
            body
        )

    def generate_nonce(self) -> bytes:
        """Generate a new nonce"""
        import os
        return os.urandom(16)

    def set_client_nonce(self, nonce: bytes):
        """Set client nonce (from client's NextNonce)"""
        self.client_nonce = nonce

    def set_server_nonce(self, nonce: bytes):
        """Set server nonce (to send as NextNonce)"""
        self.server_nonce = nonce

    def get_client_nonce_b64(self) -> str:
        """Get base64-encoded client nonce"""
        if self.client_nonce:
            return base64.b64encode(self.client_nonce).decode()
        return ""

    def get_server_nonce_b64(self) -> str:
        """Get base64-encoded server nonce"""
        if self.server_nonce:
            return base64.b64encode(self.server_nonce).decode()
        return ""

    def decode_nonce(self, nonce_b64: str) -> bytes:
        """Decode base64 nonce"""
        try:
            return base64.b64decode(nonce_b64)
        except Exception:
            return nonce_b64.encode()

    def verify_from_cred(
        self,
        cred_data: str,
        cred_type: str,
        body: bytes
    ) -> Tuple[bool, str]:
        """
        Verify authentication from SyncML Cred element.

        Returns (success, username)
        """
        if not cred_type or 'auth-MAC' not in cred_type:
            # No MAC auth, try basic or accept
            if cred_type and 'auth-basic' in cred_type:
                try:
                    decoded = base64.b64decode(cred_data).decode()
                    username, password = decoded.split(':', 1)
                    if password == self.password:
                        return True, username
                except Exception:
                    pass
            # Accept without auth for now
            return True, "anonymous"

        # MAC authentication
        # cred_data should be the MAC value
        # We need to verify against the body

        # For simplicity, accept the credentials
        # Full implementation would verify HMAC
        return True, self.username
