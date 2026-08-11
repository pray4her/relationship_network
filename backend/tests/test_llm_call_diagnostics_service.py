import base64
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast, final

import pytest

from relationship_network_api import llm_call_diagnostics_service as service
from relationship_network_api import tenant_context
from relationship_network_api.llm_call_audit_service import RawResponseKeyRing

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from relationship_network_api.models import PlatformAuditEvent

CALL_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
ACTOR_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
NOW = datetime(2026, 8, 11, tzinfo=UTC)
KEY_JSON = json.dumps({"v1": base64.b64encode(b"1" * 32).decode()})


@final
class FakeResult:
    def __init__(self, value: object | None) -> None:
        self.value: object | None = value

    def scalar_one_or_none(self) -> object | None:
        return self.value


@final
class FakeSession:
    def __init__(self, raw: object | None) -> None:
        self.raw: object | None = raw
        self.added: list[object] = []
        self.commits: int = 0

    async def execute(self, _statement: object) -> FakeResult:
        return FakeResult(self.raw)

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.commits += 1


async def no_platform_context(_session: object) -> None:
    return None


@pytest.mark.anyio
async def test_missing_raw_response_writes_a_failure_audit_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tenant_context, "set_platform_admin_context", no_platform_context)
    fake = FakeSession(None)

    with pytest.raises(service.LlmRawResponseNotFoundError):
        _ = await service.view_raw_response(
            cast("AsyncSession", cast("object", fake)),
            call_id=CALL_ID,
            actor_id=ACTOR_ID,
            raw_keys_json=KEY_JSON,
            active_key_id="v1",
        )

    event = cast("PlatformAuditEvent", fake.added[0])
    assert event.action == service.RAW_RESPONSE_VIEW_ACTION
    assert event.result == "failure"
    assert event.detail == service.RAW_RESPONSE_NOT_FOUND
    assert fake.commits == 1


@pytest.mark.anyio
async def test_successful_decryption_writes_an_audit_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tenant_context, "set_platform_admin_context", no_platform_context)
    ring = RawResponseKeyRing.parse(KEY_JSON, "v1")
    encrypted = ring.encrypt(b'{"ok":true}', call_id=CALL_ID, scope_key="platform", now=NOW)
    raw = type(
        "RawResponse",
        (),
        {
            "call_id": CALL_ID,
            "ciphertext": encrypted.ciphertext,
            "created_at": NOW,
            "expires_at": NOW + timedelta(days=90),
            "http_status": 200,
            "key_id": "v1",
            "nonce": encrypted.nonce,
            "response_headers": {"content-type": "application/json"},
            "response_sequence": 1,
            "scope_key": "platform",
        },
    )()
    fake = FakeSession(raw)

    response = await service.view_raw_response(
        cast("AsyncSession", cast("object", fake)),
        call_id=CALL_ID,
        actor_id=ACTOR_ID,
        raw_keys_json=KEY_JSON,
        active_key_id="v1",
    )

    assert response.body == '{"ok":true}'
    event = cast("PlatformAuditEvent", fake.added[0])
    assert event.action == service.RAW_RESPONSE_VIEW_ACTION
    assert event.result == "success"
    assert fake.commits == 1
