"""Password and authenticator helpers. Secrets never enter browser storage."""
import base64
import hashlib
import hmac
import json
import os
import secrets
import struct
import time
from urllib.parse import quote

from cryptography.fernet import Fernet


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return f"scrypt$16384${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, cost, salt_hex, digest_hex = stored.split('$')
        if algorithm != 'scrypt' or cost != '16384':
            return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=16384, r=8, p=1)
        return hmac.compare_digest(digest, bytes.fromhex(digest_hex))
    except (ValueError, TypeError):
        return False


def _fernet() -> Fernet:
    secret = os.getenv('APP_AUTH_SECRET') or os.getenv('APP_AUTH_PASSWORD')
    if not secret:
        raise RuntimeError('Application authentication secret is missing')
    key = hashlib.sha256(('elis-mfa-v1:' + secret).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(encrypted: str) -> str:
    return _fernet().decrypt(encrypted.encode()).decode()


def totp_uri(username: str, secret: str) -> str:
    issuer = 'Elis Group Hub'
    return f"otpauth://totp/{quote(issuer)}:{quote(username)}?secret={secret}&issuer={quote(issuer)}&digits=6&period=30"


def _totp(secret: str, counter: int) -> str:
    key = base64.b32decode(secret + '=' * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack('>Q', counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0f
    value = struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7fffffff
    return f'{value % 1000000:06d}'


def verify_totp(secret: str, code: str, now: int | None = None) -> bool:
    if len(code) != 6 or not code.isascii() or not code.isdigit():
        return False
    counter = (int(time.time()) if now is None else now) // 30
    return any(hmac.compare_digest(_totp(secret, counter + offset), code) for offset in (-1, 0, 1))


def hash_recovery_code(code: str) -> str:
    pepper = os.getenv('APP_AUTH_SECRET') or os.getenv('APP_AUTH_PASSWORD') or ''
    return hmac.new(pepper.encode(), code.strip().upper().encode(), hashlib.sha256).hexdigest()


def new_recovery_codes() -> tuple[list[str], str]:
    codes = [f'{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}' for _ in range(8)]
    return codes, json.dumps([hash_recovery_code(code) for code in codes])


def consume_recovery_code(stored: str | None, code: str) -> str | None:
    hashes = json.loads(stored or '[]')
    candidate = hash_recovery_code(code)
    for index, value in enumerate(hashes):
        if hmac.compare_digest(value, candidate):
            hashes.pop(index)
            return json.dumps(hashes)
    return None
