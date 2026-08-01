# app/core/security.py

import base64
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import secrets
from typing import Any

import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt

from app.core.config import settings

# bcrypt only uses the first 72 bytes of the password; truncate explicitly so that
# longer inputs do not raise and behave consistently across bcrypt versions.
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    pw = plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    try:
        return bcrypt.checkpw(pw, hashed_password.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


def verify_device_signature(
    device_id: str,
    timestamp: str,
    body: bytes,
    signature: str,
) -> bool:
    """Verify HMAC signature from a reader/gateway device."""
    message = f"{device_id}:{timestamp}:".encode() + body
    expected = hmac.new(
        settings.device_hmac_secret.encode(),
        message,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _device_secret_cipher() -> Fernet:
    digest = hashlib.sha256(settings.device_secret_encryption_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def generate_device_secret() -> str:
    return secrets.token_urlsafe(32)


def encrypt_device_secret(secret: str) -> str:
    return _device_secret_cipher().encrypt(secret.encode()).decode()


def decrypt_device_secret(encrypted_secret: str) -> str:
    try:
        return _device_secret_cipher().decrypt(encrypted_secret.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt device secret") from exc


def build_device_signature_v2(
    *,
    secret: str,
    method: str,
    path: str,
    device_id: str,
    timestamp: str,
    nonce: str,
    body: bytes,
) -> str:
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = (
        f"{method.upper()}\n{path}\n{device_id}\n{timestamp}\n{nonce}\n{body_hash}"
    ).encode()
    return hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()


def verify_device_signature_v2(
    *,
    secret: str,
    method: str,
    path: str,
    device_id: str,
    timestamp: str,
    nonce: str,
    body: bytes,
    signature: str,
) -> bool:
    expected = build_device_signature_v2(
        secret=secret,
        method=method,
        path=path,
        device_id=device_id,
        timestamp=timestamp,
        nonce=nonce,
        body=body,
    )
    return hmac.compare_digest(expected, signature)


def extract_token_subject(token: str) -> str:
    try:
        payload = decode_access_token(token)
    except JWTError as exc:
        raise ValueError("Invalid token") from exc
    subject = payload.get("sub")
    if not subject:
        raise ValueError("Token missing subject")
    return str(subject)
