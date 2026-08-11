from __future__ import annotations

import base64
import binascii
import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final, cast, final

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import func, insert, select, text

from relationship_network_api import tenant_context
from relationship_network_api.models import (
    LlmCallMetadataEvent,
    LlmCallOutcomeEvent,
    LlmCallRecord,
    LlmRawResponse,
    PlatformOutboxEvent,
    TenantOutboxEvent,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from relationship_network_api.openrouter import (
        OpenRouterProbeResult,
        OpenRouterRequirementResult,
        OpenRouterResponseExchange,
    )

RAW_RESPONSE_RETENTION_DAYS: Final = 90
_AES_256_KEY_BYTES: Final = 32
_AES_GCM_NONCE_BYTES: Final = 12
_SENSITIVE_RESPONSE_HEADERS: Final = frozenset(
    {
        "authorization",
        "proxy-authenticate",
        "proxy-authorization",
        "set-cookie",
        "www-authenticate",
    }
)
LLM_METADATA_OUTBOX_TOPIC: Final = "llm_call_metadata.fetch"
INITIAL_METADATA_RETRY_SECONDS: Final = 30


class RawResponseKeyConfigurationError(ValueError):
    """Raised when the active AES-GCM key ring is not deployable."""


class HistoricalRawResponseKeyUnavailableError(RuntimeError):
    """Raised when a retained ciphertext references a removed historical key."""


class RawResponseAuthenticationError(RuntimeError):
    """Raised when AES-GCM authentication rejects ciphertext, nonce, or AAD."""


@final
@dataclass(frozen=True)
class EncryptedRawResponse:
    key_id: str
    nonce: bytes
    ciphertext: bytes
    expires_at: datetime


@final
@dataclass(frozen=True)
class PersistedCallResponse:
    outcome: str
    sequence_number: int
    is_late_response: bool


@final
class RawResponseKeyRing:
    """Versioned AES-256-GCM keys loaded only from deployment configuration."""

    def __init__(self, keys: dict[str, bytes], active_key_id: str) -> None:
        self._keys = dict(keys)
        self.active_key_id = active_key_id

    @classmethod
    def parse(cls, raw_json: str, active_key_id: str) -> RawResponseKeyRing:
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError as error:
            message = "RN_LLM_RAW_RESPONSE_KEYS must be a JSON object"
            raise RawResponseKeyConfigurationError(message) from error
        if not isinstance(payload, dict):
            message = "RN_LLM_RAW_RESPONSE_KEYS must be a JSON object"
            raise RawResponseKeyConfigurationError(message)
        keys: dict[str, bytes] = {}
        for raw_key_id, raw_key in payload.items():
            if not isinstance(raw_key_id, str) or not raw_key_id.strip():
                message = "LLM raw response key IDs must be non-empty strings"
                raise RawResponseKeyConfigurationError(message)
            if not isinstance(raw_key, str):
                message = f"LLM raw response key {raw_key_id!r} must be Base64 text"
                raise RawResponseKeyConfigurationError(message)
            try:
                decoded = base64.b64decode(raw_key, validate=True)
            except (binascii.Error, ValueError) as error:
                message = f"LLM raw response key {raw_key_id!r} is not valid Base64"
                raise RawResponseKeyConfigurationError(message) from error
            if len(decoded) != _AES_256_KEY_BYTES:
                message = f"LLM raw response key {raw_key_id!r} must decode to 32 bytes"
                raise RawResponseKeyConfigurationError(message)
            keys[raw_key_id] = decoded
        return cls(keys, active_key_id.strip())

    def require_active_key(self) -> bytes:
        if not self.active_key_id or self.active_key_id not in self._keys:
            message = "active LLM raw response key is not present in the key ring"
            raise RawResponseKeyConfigurationError(message)
        return self._keys[self.active_key_id]

    def encrypt(
        self,
        plaintext: bytes,
        *,
        call_id: uuid.UUID,
        scope_key: str,
        now: datetime | None = None,
    ) -> EncryptedRawResponse:
        key = self.require_active_key()
        nonce = os.urandom(_AES_GCM_NONCE_BYTES)
        aad = raw_response_aad(call_id, scope_key, self.active_key_id)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)
        created_at = now or datetime.now(UTC)
        return EncryptedRawResponse(
            key_id=self.active_key_id,
            nonce=nonce,
            ciphertext=ciphertext,
            expires_at=created_at + timedelta(days=RAW_RESPONSE_RETENTION_DAYS),
        )

    def decrypt(
        self,
        ciphertext: bytes,
        *,
        nonce: bytes,
        call_id: uuid.UUID,
        scope_key: str,
        key_id: str,
    ) -> bytes:
        key = self._keys.get(key_id)
        if key is None:
            raise HistoricalRawResponseKeyUnavailableError(key_id)
        try:
            return AESGCM(key).decrypt(
                nonce,
                ciphertext,
                raw_response_aad(call_id, scope_key, key_id),
            )
        except InvalidTag as error:
            raise RawResponseAuthenticationError from error


def raw_response_aad(call_id: uuid.UUID, scope_key: str, key_id: str) -> bytes:
    """Build the stable, non-secret authenticated context for one ciphertext."""
    return f"{call_id}:{scope_key}:{key_id}".encode()


async def acquire_call_transaction_lock(session: AsyncSession, call_id: uuid.UUID) -> None:
    """Serialize append-only call events without requiring UPDATE table privileges."""
    lock_key = int.from_bytes(call_id.bytes[:8], byteorder="big", signed=True)
    _ = await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": lock_key},
    )


def sanitize_response_headers(headers: dict[str, str]) -> dict[str, object]:
    """Retain response diagnostics while excluding authentication and cookie material."""
    return {
        key.lower(): value
        for key, value in headers.items()
        if key.lower() not in _SENSITIVE_RESPONSE_HEADERS
    }


def parse_json_object(raw_body: bytes) -> dict[str, object] | None:
    try:
        parsed = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return cast("dict[str, object]", parsed) if isinstance(parsed, dict) else None


async def persist_call_response(  # noqa: PLR0913
    session_factory: async_sessionmaker[AsyncSession],
    *,
    call_id: uuid.UUID,
    key_ring: RawResponseKeyRing,
    requested_outcome: str,
    category: str,
    exchange: OpenRouterResponseExchange | None,
    result: OpenRouterProbeResult | OpenRouterRequirementResult | None,
    duration_ms: int,
    tenant_id: uuid.UUID | None = None,
) -> PersistedCallResponse:
    """Atomically retain raw bytes, outcome, and initial metadata before business commit."""
    async with session_factory() as session, session.begin():
        if tenant_id is not None:
            await tenant_context.set_tenant_context(session, tenant_id)
        await acquire_call_transaction_lock(session, call_id)
        call = (
            await session.execute(select(LlmCallRecord).where(LlmCallRecord.id == call_id))
        ).scalar_one()
        previous = list(
            (
                await session.execute(
                    select(LlmCallOutcomeEvent)
                    .where(LlmCallOutcomeEvent.call_id == call_id)
                    .order_by(LlmCallOutcomeEvent.sequence_number)
                )
            ).scalars()
        )
        if previous:
            last = previous[-1]
            if last.outcome != "outcome_unknown" or len(previous) > 1:
                return PersistedCallResponse(
                    outcome=last.outcome,
                    sequence_number=last.sequence_number,
                    is_late_response=last.outcome == "late_response",
                )
            outcome = "late_response"
            sequence_number = 2
        else:
            outcome = requested_outcome
            sequence_number = 1

        if exchange is not None:
            encrypted = key_ring.encrypt(
                exchange.raw_body,
                call_id=call.id,
                scope_key=call.scope_key,
            )
            session.add(
                LlmRawResponse(
                    id=uuid.uuid4(),
                    call_id=call.id,
                    response_sequence=sequence_number,
                    scope=call.scope,
                    tenant_id=call.tenant_id,
                    key_id=encrypted.key_id,
                    nonce=encrypted.nonce,
                    ciphertext=encrypted.ciphertext,
                    http_status=exchange.status_code,
                    response_headers=sanitize_response_headers(exchange.headers),
                    expires_at=encrypted.expires_at,
                )
            )
            await session.flush()

        session.add(
            LlmCallOutcomeEvent(
                call_id=call.id,
                sequence_number=sequence_number,
                scope=call.scope,
                tenant_id=call.tenant_id,
                outcome=outcome,
                category=category,
                provider_request_id=None if result is None else result.provider_request_id,
                actual_model=None if result is None else result.actual_model,
                actual_provider=None if result is None else result.actual_provider,
                http_status=None if exchange is None else exchange.status_code,
                duration_ms=duration_ms,
            )
        )
        await _append_initial_metadata(
            session,
            call=call,
            exchange=exchange,
            result=result,
        )
        return PersistedCallResponse(
            outcome=outcome,
            sequence_number=sequence_number,
            is_late_response=outcome == "late_response",
        )


async def _append_initial_metadata(
    session: AsyncSession,
    *,
    call: LlmCallRecord,
    exchange: OpenRouterResponseExchange | None,
    result: OpenRouterProbeResult | OpenRouterRequirementResult | None,
) -> None:
    existing = (
        await session.execute(
            select(func.count())
            .select_from(LlmCallMetadataEvent)
            .where(LlmCallMetadataEvent.call_id == call.id)
        )
    ).scalar_one()
    if int(existing) > 0:
        return
    body = None if exchange is None else parse_json_object(exchange.raw_body)
    usage_raw = None if body is None else body.get("usage")
    usage = cast("dict[str, object]", usage_raw) if isinstance(usage_raw, dict) else {}
    generation_id = (
        result.provider_request_id
        if result is not None
        else _optional_text(None if body is None else body.get("id"))
    )
    prompt_tokens = _optional_nonnegative_int(usage.get("prompt_tokens"))
    completion_tokens = _optional_nonnegative_int(usage.get("completion_tokens"))
    total_tokens = _optional_nonnegative_int(usage.get("total_tokens"))
    cost = _optional_nonnegative_float(usage.get("cost"))
    has_usage = any(
        value is not None for value in (prompt_tokens, completion_tokens, total_tokens, cost)
    )
    if has_usage:
        status = "available"
        next_retry_at = None
        error_category = ""
    elif generation_id is not None:
        status = "retry_scheduled"
        next_retry_at = datetime.now(UTC) + timedelta(seconds=INITIAL_METADATA_RETRY_SECONDS)
        error_category = "metadata_pending"
    else:
        status = "unavailable"
        next_retry_at = None
        error_category = "generation_id_unavailable"
    session.add(
        LlmCallMetadataEvent(
            call_id=call.id,
            sequence_number=1,
            scope=call.scope,
            tenant_id=call.tenant_id,
            status=status,
            generation_id=generation_id,
            actual_model=None if result is None else result.actual_model,
            actual_provider=None if result is None else result.actual_provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            source="response",
            next_retry_at=next_retry_at,
            error_category=error_category,
        )
    )
    if next_retry_at is not None and call.scope == "platform":
        _ = await session.execute(
            insert(PlatformOutboxEvent)
            .inline()
            .values(
                id=uuid.uuid4(),
                topic=LLM_METADATA_OUTBOX_TOPIC,
                aggregate_id=call.id,
                available_at=next_retry_at,
            )
        )
    elif next_retry_at is not None:
        task_id = call.job_requirement_parsing_task_id
        if task_id is None or call.tenant_id is None:
            message = "tenant metadata Outbox requires tenant task identity"
            raise RuntimeError(message)
        session.add(
            TenantOutboxEvent(
                id=uuid.uuid4(),
                tenant_id=call.tenant_id,
                topic=LLM_METADATA_OUTBOX_TOPIC,
                aggregate_id=call.id,
                job_requirement_parsing_task_id=task_id,
                available_at=next_retry_at,
            )
        )


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_nonnegative_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _optional_nonnegative_float(value: object) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    parsed = float(value)
    return parsed if parsed >= 0 else None
