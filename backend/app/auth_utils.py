"""
Lightweight HMAC-signed session tokens for app authentication.
"""
import base64
import hmac
import hashlib
import json
import os
import time
from typing import Optional, Tuple

# Config
SESSION_COOKIE_NAME = "session_token"
SESSION_DURATION_SECONDS = int(os.getenv("APP_SESSION_DURATION_SECONDS", 60 * 60 * 12))  # 12 hours default


def _get_secret() -> Optional[bytes]:
    secret = os.getenv("APP_AUTH_SECRET") or os.getenv("APP_AUTH_PASSWORD")
    if not secret:
        return None
    return secret.encode("utf-8")


def _sign(message: str, secret: bytes) -> str:
    return hmac.new(secret, message.encode("utf-8"), hashlib.sha256).hexdigest()


def create_session_token(username: str) -> Optional[str]:
    """
    Create a signed session token for the given username.
    """
    secret = _get_secret()
    if not secret:
        return None

    payload = {
        "u": username,
        "exp": int(time.time()) + SESSION_DURATION_SECONDS,
        "v": 1,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")
    signature = _sign(payload_b64, secret)
    return f"{payload_b64}.{signature}"


def verify_session_token(token: str) -> Tuple[bool, Optional[str]]:
    """
    Verify a session token. Returns (valid, username).
    """
    secret = _get_secret()
    if not secret or not token or "." not in token:
        return False, None

    payload_b64, provided_sig = token.rsplit(".", 1)
    expected_sig = _sign(payload_b64, secret)
    if not hmac.compare_digest(provided_sig, expected_sig):
        return False, None

    # Pad base64 string if needed
    padding = "=" * (-len(payload_b64) % 4)
    try:
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return False, None

    if payload.get("exp", 0) < int(time.time()):
        return False, None

    username = payload.get("u")
    return True, username
