import base64

from relationship_network_api.security import (
    DUMMY_PASSWORD_HASH,
    generate_session_token,
    generate_totp_secret,
    hash_password,
    hash_session_token,
    totp_code,
    verify_password,
    verify_totp,
)


def test_password_hash_round_trip() -> None:
    # Given a plaintext password
    password = "sup3r-secret-password"

    # When it is hashed and then verified
    password_hash = hash_password(password)

    # Then verification succeeds and the hash does not expose the plaintext
    assert verify_password(password_hash=password_hash, password=password)
    assert password not in password_hash


def test_verify_password_rejects_wrong_password() -> None:
    # Given a stored password hash
    password_hash = hash_password("correct-horse-battery")

    # When a different password is verified
    # Then verification fails instead of raising
    assert not verify_password(password_hash=password_hash, password="correct-horse-batterx")


def test_dummy_hash_supports_timing_safe_verification() -> None:
    # Given the precomputed dummy hash used for unknown accounts
    # When a password is verified against it
    # Then verification runs and fails without raising
    assert not verify_password(password_hash=DUMMY_PASSWORD_HASH, password="anything-goes-123")


def test_session_token_hash_is_deterministic_and_opaque() -> None:
    # Given an opaque session token
    token = generate_session_token()

    # When it is hashed twice
    first = hash_session_token(token)
    second = hash_session_token(token)

    # Then the hash is deterministic, fixed length, and never contains the raw token
    assert first == second
    assert len(first) == 64
    assert token not in first


def test_session_tokens_are_unique() -> None:
    # Given two generated session tokens
    # When they are compared
    # Then they never collide
    assert generate_session_token() != generate_session_token()


def test_totp_secret_is_base32_without_padding() -> None:
    # Given two generated TOTP secrets
    first = generate_totp_secret()
    second = generate_totp_secret()

    # Then they are RFC 4648 base32 without padding and never collide
    assert first != second
    assert len(first) == 32
    assert "=" not in first
    assert base64.b32decode(first + "=" * (-len(first) % 8))


def test_totp_matches_rfc6238_sha1_vectors() -> None:
    # Given the RFC 6238 appendix B seed encoded as base32
    secret = base64.b32encode(b"12345678901234567890").decode("ascii")

    # When the 8-digit codes are computed at the pinned timestamps
    # Then they match the RFC 6238 HMAC-SHA1 test values
    assert totp_code(secret, at_time=59, digits=8) == "94287082"
    assert totp_code(secret, at_time=1111111109, digits=8) == "07081804"
    assert totp_code(secret, at_time=1234567890, digits=8) == "89005924"


def test_totp_code_round_trip_with_default_digits() -> None:
    # Given a generated secret and a fixed time
    secret = generate_totp_secret()
    at_time = 1700000000

    # When a 6-digit code is computed
    code = totp_code(secret, at_time=at_time)

    # Then it verifies at that time
    assert len(code) == 6
    assert code.isdigit()
    assert verify_totp(secret, code, at_time=at_time)


def test_verify_totp_accepts_codes_within_window() -> None:
    # Given a code generated one step in the past and one in the future
    secret = generate_totp_secret()
    at_time = 1700000000
    previous = totp_code(secret, at_time=at_time - 30)
    upcoming = totp_code(secret, at_time=at_time + 30)
    distant = totp_code(secret, at_time=at_time + 60)

    # Then the default window of one step accepts neighbours but not beyond
    assert verify_totp(secret, previous, at_time=at_time)
    assert verify_totp(secret, upcoming, at_time=at_time)
    assert not verify_totp(secret, distant, at_time=at_time)


def test_verify_totp_rejects_malformed_codes() -> None:
    # Given a valid secret
    secret = generate_totp_secret()

    # When malformed codes are verified
    # Then verification fails instead of raising
    assert not verify_totp(secret, "not-a-code", at_time=1700000000)
    assert not verify_totp(secret, "", at_time=1700000000)
    assert not verify_totp("not!!base32", "123456", at_time=1700000000)
