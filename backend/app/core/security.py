"""
CascadeX security utilities — Argon2 hashing, JWT creation/decoding, and OTP generation.

All operations use secure cryptographic algorithms and read secrets/settings
from app.core.config.
"""

import random
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError
from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.core.config import settings

# Password hasher instance (Argon2id)
_ph = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return _ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    try:
        return _ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, InvalidHash):
        return False


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a short-lived JWT access token."""
    to_encode = data.copy()
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    to_encode.update({
        "exp": expire,
        "iat": now,
        "type": "access",
        "jti": secrets.token_hex(16),
    })
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a long-lived JWT refresh token."""
    to_encode = data.copy()
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.jwt_refresh_token_expire_days)

    to_encode.update({
        "exp": expire,
        "iat": now,
        "type": "refresh",
        "jti": secrets.token_hex(16),
    })
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token.

    Raises:
        HTTPException(401): If token is invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": f"Token verification failed: {str(e)}"},
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


def generate_otp() -> str:
    """Generate a 6-digit numeric OTP."""
    return f"{random.randint(100000, 999999)}"


def hash_otp(otp: str) -> str:
    """Hash an OTP for safe storage."""
    return hash_password(otp)


def verify_otp(otp: str, hashed_otp: str) -> bool:
    """Verify a raw OTP against its hash."""
    return verify_password(otp, hashed_otp)


# ---------------------------------------------------------------------------
# Field-level encryption — Phase 09
# ---------------------------------------------------------------------------

def _fernet_instance():
    """Return a Fernet instance configured from settings.field_encryption_key.

    Returns None when the key is empty (dev/test passthrough mode).

    Raises:
        ValueError: If the key is non-empty but not a valid Fernet key.
    """
    key = settings.field_encryption_key.strip()
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet  # type: ignore[import]
        return Fernet(key.encode())
    except Exception as exc:
        raise ValueError(
            f"FIELD_ENCRYPTION_KEY is invalid — must be a URL-safe base64-encoded 32-byte Fernet key: {exc}"
        ) from exc


def encrypt_field(plaintext: str) -> str:
    """Encrypt a sensitive string field for storage in Neo4j.

    When ``settings.field_encryption_key`` is empty (dev/test mode) the
    plaintext is returned unchanged — encryption is explicitly disabled.

    Applied to: ``ScanRecord.ocr_text`` on write (scans.py).

    Args:
        plaintext: The raw sensitive string to encrypt.

    Returns:
        A URL-safe base64 Fernet token string, or the original ``plaintext``
        if encryption is disabled (no key configured).
    """
    fernet = _fernet_instance()
    if fernet is None:
        return plaintext  # dev/test passthrough
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt_field(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted field read from Neo4j.

    When ``settings.field_encryption_key`` is empty the ciphertext (which is
    actually plaintext in passthrough mode) is returned unchanged.

    Args:
        ciphertext: A Fernet token string produced by ``encrypt_field``.

    Returns:
        The original plaintext string.

    Raises:
        cryptography.fernet.InvalidToken: If the token is corrupted or the
            wrong key is used.
    """
    fernet = _fernet_instance()
    if fernet is None:
        return ciphertext  # dev/test passthrough
    return fernet.decrypt(ciphertext.encode()).decode()

