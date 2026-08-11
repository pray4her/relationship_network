import base64
import json
import uuid
from datetime import UTC, datetime

import pytest

from relationship_network_api.llm_call_audit_service import (
    HistoricalRawResponseKeyUnavailableError,
    RawResponseAuthenticationError,
    RawResponseKeyConfigurationError,
    RawResponseKeyRing,
    sanitize_response_headers,
)

CALL_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")


def encoded_key(byte: int) -> str:
    return base64.b64encode(bytes([byte]) * 32).decode()


def key_ring(*, active: str = "v1", include_v1: bool = True) -> RawResponseKeyRing:
    keys = {"v2": encoded_key(2)}
    if include_v1:
        keys["v1"] = encoded_key(1)
    return RawResponseKeyRing.parse(json.dumps(keys), active)


def test_aes_gcm_round_trip_uses_unique_nonce_and_90_day_expiry() -> None:
    ring = key_ring()
    now = datetime(2026, 8, 11, tzinfo=UTC)

    first = ring.encrypt(b'{"ok":true}', call_id=CALL_ID, scope_key="platform", now=now)
    second = ring.encrypt(b'{"ok":true}', call_id=CALL_ID, scope_key="platform", now=now)

    assert len(first.nonce) == 12
    assert first.nonce != second.nonce
    assert first.expires_at.isoformat() == "2026-11-09T00:00:00+00:00"
    assert (
        ring.decrypt(
            first.ciphertext,
            nonce=first.nonce,
            call_id=CALL_ID,
            scope_key="platform",
            key_id=first.key_id,
        )
        == b'{"ok":true}'
    )


@pytest.mark.parametrize("tamper", ["ciphertext", "aad", "key"])
def test_aes_gcm_rejects_ciphertext_aad_and_key_tampering(tamper: str) -> None:
    ring = key_ring()
    encrypted = ring.encrypt(b"secret", call_id=CALL_ID, scope_key="platform")
    ciphertext = encrypted.ciphertext
    scope_key = "platform"
    decrypt_ring = ring
    if tamper == "ciphertext":
        ciphertext = encrypted.ciphertext[:-1] + bytes([encrypted.ciphertext[-1] ^ 1])
    elif tamper == "aad":
        scope_key = "different"
    else:
        decrypt_ring = RawResponseKeyRing.parse(json.dumps({"v1": encoded_key(9)}), "v1")

    with pytest.raises(RawResponseAuthenticationError):
        _ = decrypt_ring.decrypt(
            ciphertext,
            nonce=encrypted.nonce,
            call_id=CALL_ID,
            scope_key=scope_key,
            key_id="v1",
        )


def test_key_rotation_reads_history_and_rejects_missing_history() -> None:
    old_ring = key_ring(active="v1")
    encrypted = old_ring.encrypt(b"history", call_id=CALL_ID, scope_key="platform")
    rotated = key_ring(active="v2")
    assert (
        rotated.decrypt(
            encrypted.ciphertext,
            nonce=encrypted.nonce,
            call_id=CALL_ID,
            scope_key="platform",
            key_id="v1",
        )
        == b"history"
    )

    with pytest.raises(HistoricalRawResponseKeyUnavailableError):
        _ = key_ring(active="v2", include_v1=False).decrypt(
            encrypted.ciphertext,
            nonce=encrypted.nonce,
            call_id=CALL_ID,
            scope_key="platform",
            key_id="v1",
        )


@pytest.mark.parametrize(
    ("raw", "active"),
    [("[]", "v1"), ("not-json", "v1"), (json.dumps({"v1": "short"}), "v1")],
)
def test_invalid_key_ring_is_rejected(raw: str, active: str) -> None:
    with pytest.raises(RawResponseKeyConfigurationError):
        _ = RawResponseKeyRing.parse(raw, active)


def test_response_header_sanitization_excludes_credentials_and_cookies() -> None:
    assert sanitize_response_headers(
        {
            "Content-Type": "application/json",
            "Set-Cookie": "secret=value",
            "WWW-Authenticate": "Bearer secret",
            "X-Request-ID": "request-1",
        }
    ) == {"content-type": "application/json", "x-request-id": "request-1"}
