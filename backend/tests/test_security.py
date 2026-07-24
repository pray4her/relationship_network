from relationship_network_api.security import (
    DUMMY_PASSWORD_HASH,
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
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
