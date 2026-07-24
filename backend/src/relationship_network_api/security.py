import hashlib
import secrets
from typing import Final

from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, VerificationError

_TOKEN_BYTES: Final = 32

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
