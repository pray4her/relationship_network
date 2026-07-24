import base64
import hashlib
import hmac
import secrets
import struct
from typing import Final

from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, VerificationError

_TOKEN_BYTES: Final = 32
_TOTP_SECRET_BYTES: Final = 20
_TOTP_DEFAULT_STEP: Final = 30
_TOTP_DEFAULT_DIGITS: Final = 6

_password_hasher: Final = PasswordHasher()

DUMMY_PASSWORD_HASH: Final = _password_hasher.hash(secrets.token_urlsafe(_TOKEN_BYTES))
"""Precomputed argon2 hash used to equalize login timing for unknown emails."""


def hash_password(password: str) -> str:
    """Hash a plaintext password with argon2id."""
    return _password_hasher.hash(password)


def verify_password(*, password_hash: str, password: str) -> bool:
    """Return whether the plaintext password matches the stored argon2 hash."""
    try:
        return _password_hasher.verify(password_hash, password)
    except (Argon2Error, VerificationError):
        return False


def generate_session_token() -> str:
    """Generate an opaque URL-safe session token."""
    return secrets.token_urlsafe(_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    """Return the SHA-256 hex digest stored in place of the raw session token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_totp_secret() -> str:
    """Generate a base32-encoded TOTP secret without padding."""
    return base64.b32encode(secrets.token_bytes(_TOTP_SECRET_BYTES)).decode("ascii").rstrip("=")


def totp_code(
    secret: str,
    *,
    at_time: int,
    step: int = _TOTP_DEFAULT_STEP,
    digits: int = _TOTP_DEFAULT_DIGITS,
) -> str:
    """Compute the RFC 6238 HMAC-SHA1 TOTP code for the given timestamp."""
    key = _decode_totp_secret(secret)
    counter = at_time // step
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    truncated = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(truncated % 10**digits).zfill(digits)


def verify_totp(  # noqa: PLR0913
    secret: str,
    code: str,
    *,
    at_time: int,
    window: int = 1,
    step: int = _TOTP_DEFAULT_STEP,
    digits: int = _TOTP_DEFAULT_DIGITS,
) -> bool:
    """Constant-time TOTP verification accepting codes within ±window steps."""
    if not code.isdigit() or len(code) != digits:
        return False
    try:
        normalized = _normalize_secret(secret)
    except ValueError:
        return False
    candidate = code.encode("ascii")
    for offset in range(-window, window + 1):
        expected = totp_code(
            normalized,
            at_time=at_time + offset * step,
            step=step,
            digits=digits,
        ).encode("ascii")
        if hmac.compare_digest(expected, candidate):
            return True
    return False


def _normalize_secret(secret: str) -> str:
    """Validate a base32 TOTP secret, raising ValueError when malformed."""
    _ = base64.b32decode(_pad_base32(secret))
    return secret


def _decode_totp_secret(secret: str) -> bytes:
    return base64.b32decode(_pad_base32(secret))


def _pad_base32(secret: str) -> bytes:
    return (secret + "=" * (-len(secret) % 8)).encode("ascii")
