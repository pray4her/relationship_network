from __future__ import annotations

import base64
import binascii
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, cast, final

from sqlalchemy import and_, exists, func, or_, select

from relationship_network_api import audit_service, tenant_context
from relationship_network_api.llm_call_audit_service import (
    HistoricalRawResponseKeyUnavailableError,
    RawResponseAuthenticationError,
    RawResponseKeyConfigurationError,
    RawResponseKeyRing,
)
from relationship_network_api.models import (
    LlmCallMetadataEvent,
    LlmCallOutcomeEvent,
    LlmCallRecord,
    LlmRawResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

CALL_NOT_FOUND: Final = "llm_call_not_found"
RAW_RESPONSE_NOT_FOUND: Final = "llm_raw_response_not_found"
RAW_RESPONSE_KEY_UNAVAILABLE: Final = "llm_raw_response_key_unavailable"
RAW_RESPONSE_DECRYPTION_FAILED: Final = "llm_raw_response_decryption_failed"
RAW_RESPONSE_VIEW_ACTION: Final = "llm_raw_response.view"
PAGE_SIZE: Final = 50


class LlmCallNotFoundError(RuntimeError):
    pass


class LlmRawResponseNotFoundError(RuntimeError):
    pass


class LlmRawResponseKeyUnavailableError(RuntimeError):
    pass


class LlmRawResponseDecryptionError(RuntimeError):
    pass


class InvalidLlmCallCursorError(ValueError):
    pass


@final
@dataclass(frozen=True)
class LlmCallSummaryView:
    id: uuid.UUID
    scope: str
    tenant_id: uuid.UUID | None
    call_type: str
    model: str
    request_number: int
    platform_attempt_id: uuid.UUID | None
    job_requirement_parsing_task_id: uuid.UUID | None
    outcome: str | None
    metadata_status: str | None
    raw_response_available: bool
    created_at: datetime


@final
@dataclass(frozen=True)
class LlmCallPageView:
    calls: list[LlmCallSummaryView]
    next_cursor: str | None


@final
@dataclass(frozen=True)
class LlmCallOutcomeView:
    sequence_number: int
    outcome: str
    category: str
    provider_request_id: str | None
    actual_model: str | None
    actual_provider: str | None
    http_status: int | None
    duration_ms: int | None
    created_at: datetime


@final
@dataclass(frozen=True)
class LlmCallMetadataView:
    sequence_number: int
    status: str
    generation_id: str | None
    actual_model: str | None
    actual_provider: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    cost: float | None
    source: str
    next_retry_at: datetime | None
    error_category: str
    created_at: datetime


@final
@dataclass(frozen=True)
class LlmCallDetailView:
    call: LlmCallRecord
    outcomes: list[LlmCallOutcomeView]
    metadata_events: list[LlmCallMetadataView]
    raw_response_available: bool
    raw_response_expires_at: datetime | None


@final
@dataclass(frozen=True)
class DecryptedRawResponseView:
    body: str
    encoding: str
    content_type: str | None
    http_status: int | None
    response_sequence: int
    created_at: datetime
    expires_at: datetime


async def list_calls(  # noqa: C901, PLR0913
    session: AsyncSession,
    *,
    scope: str | None,
    call_type: str | None,
    outcome: str | None,
    metadata_status: str | None,
    tenant_id: uuid.UUID | None,
    platform_attempt_id: uuid.UUID | None,
    created_from: datetime | None,
    created_to: datetime | None,
    cursor: str | None,
) -> LlmCallPageView:
    await tenant_context.set_platform_admin_context(session)
    latest_outcome = (
        select(LlmCallOutcomeEvent.outcome)
        .where(LlmCallOutcomeEvent.call_id == LlmCallRecord.id)
        .order_by(LlmCallOutcomeEvent.sequence_number.desc())
        .limit(1)
        .correlate(LlmCallRecord)
        .scalar_subquery()
    )
    latest_metadata = (
        select(LlmCallMetadataEvent.status)
        .where(LlmCallMetadataEvent.call_id == LlmCallRecord.id)
        .order_by(LlmCallMetadataEvent.sequence_number.desc())
        .limit(1)
        .correlate(LlmCallRecord)
        .scalar_subquery()
    )
    raw_available = exists(
        select(LlmRawResponse.id).where(
            LlmRawResponse.call_id == LlmCallRecord.id,
            LlmRawResponse.expires_at > func.now(),
        )
    )
    statement = select(
        LlmCallRecord,
        latest_outcome.label("latest_outcome"),
        latest_metadata.label("latest_metadata"),
        raw_available.label("raw_available"),
    )
    if scope is not None:
        statement = statement.where(LlmCallRecord.scope == scope)
    if call_type is not None:
        statement = statement.where(LlmCallRecord.call_type == call_type)
    if outcome is not None:
        statement = statement.where(latest_outcome == outcome)
    if metadata_status is not None:
        statement = statement.where(latest_metadata == metadata_status)
    if tenant_id is not None:
        statement = statement.where(LlmCallRecord.tenant_id == tenant_id)
    if platform_attempt_id is not None:
        statement = statement.where(LlmCallRecord.platform_attempt_id == platform_attempt_id)
    if created_from is not None:
        statement = statement.where(LlmCallRecord.created_at >= created_from)
    if created_to is not None:
        statement = statement.where(LlmCallRecord.created_at <= created_to)
    if cursor is not None:
        cursor_created_at, cursor_id = decode_cursor(cursor)
        statement = statement.where(
            or_(
                LlmCallRecord.created_at < cursor_created_at,
                and_(
                    LlmCallRecord.created_at == cursor_created_at,
                    LlmCallRecord.id < cursor_id,
                ),
            )
        )
    rows = (
        await session.execute(
            statement.order_by(LlmCallRecord.created_at.desc(), LlmCallRecord.id.desc()).limit(
                PAGE_SIZE + 1
            )
        )
    ).all()
    page_rows = rows[:PAGE_SIZE]
    calls = [
        LlmCallSummaryView(
            id=row.LlmCallRecord.id,
            scope=row.LlmCallRecord.scope,
            tenant_id=row.LlmCallRecord.tenant_id,
            call_type=row.LlmCallRecord.call_type,
            model=row.LlmCallRecord.model,
            request_number=row.LlmCallRecord.request_number,
            platform_attempt_id=row.LlmCallRecord.platform_attempt_id,
            job_requirement_parsing_task_id=row.LlmCallRecord.job_requirement_parsing_task_id,
            outcome=row.latest_outcome,
            metadata_status=row.latest_metadata,
            raw_response_available=bool(row.raw_available),
            created_at=row.LlmCallRecord.created_at,
        )
        for row in page_rows
    ]
    next_cursor = None
    if len(rows) > PAGE_SIZE and calls:
        last = calls[-1]
        next_cursor = encode_cursor(last.created_at, last.id)
    return LlmCallPageView(calls=calls, next_cursor=next_cursor)


async def get_call_detail(session: AsyncSession, *, call_id: uuid.UUID) -> LlmCallDetailView:
    await tenant_context.set_platform_admin_context(session)
    call = (
        await session.execute(select(LlmCallRecord).where(LlmCallRecord.id == call_id))
    ).scalar_one_or_none()
    if call is None:
        raise LlmCallNotFoundError(CALL_NOT_FOUND)
    outcomes = list(
        (
            await session.execute(
                select(LlmCallOutcomeEvent)
                .where(LlmCallOutcomeEvent.call_id == call_id)
                .order_by(LlmCallOutcomeEvent.sequence_number)
            )
        ).scalars()
    )
    metadata_events = list(
        (
            await session.execute(
                select(LlmCallMetadataEvent)
                .where(LlmCallMetadataEvent.call_id == call_id)
                .order_by(LlmCallMetadataEvent.sequence_number)
            )
        ).scalars()
    )
    raw_expires_at = cast(
        "datetime | None",
        (
            await session.execute(
                select(func.max(LlmRawResponse.expires_at)).where(
                    LlmRawResponse.call_id == call_id,
                    LlmRawResponse.expires_at > func.now(),
                )
            )
        ).scalar_one(),
    )
    return LlmCallDetailView(
        call=call,
        outcomes=[_outcome_view(event) for event in outcomes],
        metadata_events=[_metadata_view(event) for event in metadata_events],
        raw_response_available=raw_expires_at is not None,
        raw_response_expires_at=raw_expires_at,
    )


async def view_raw_response(
    session: AsyncSession,
    *,
    call_id: uuid.UUID,
    actor_id: uuid.UUID,
    raw_keys_json: str,
    active_key_id: str,
) -> DecryptedRawResponseView:
    await tenant_context.set_platform_admin_context(session)
    raw = (
        await session.execute(
            select(LlmRawResponse)
            .where(
                LlmRawResponse.call_id == call_id,
                LlmRawResponse.expires_at > func.now(),
            )
            .order_by(LlmRawResponse.response_sequence.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if raw is None:
        await _audit_raw_view(
            session,
            call_id=call_id,
            actor_id=actor_id,
            result=audit_service.AUDIT_RESULT_FAILURE,
            detail=RAW_RESPONSE_NOT_FOUND,
        )
        raise LlmRawResponseNotFoundError(RAW_RESPONSE_NOT_FOUND)
    try:
        key_ring = RawResponseKeyRing.parse(raw_keys_json, active_key_id)
        plaintext = key_ring.decrypt(
            raw.ciphertext,
            nonce=raw.nonce,
            call_id=raw.call_id,
            scope_key=raw.scope_key,
            key_id=raw.key_id,
        )
    except (HistoricalRawResponseKeyUnavailableError, RawResponseKeyConfigurationError) as error:
        await _audit_raw_view(
            session,
            call_id=call_id,
            actor_id=actor_id,
            result=audit_service.AUDIT_RESULT_FAILURE,
            detail=RAW_RESPONSE_KEY_UNAVAILABLE,
        )
        raise LlmRawResponseKeyUnavailableError(RAW_RESPONSE_KEY_UNAVAILABLE) from error
    except RawResponseAuthenticationError as error:
        await _audit_raw_view(
            session,
            call_id=call_id,
            actor_id=actor_id,
            result=audit_service.AUDIT_RESULT_FAILURE,
            detail=RAW_RESPONSE_DECRYPTION_FAILED,
        )
        raise LlmRawResponseDecryptionError(RAW_RESPONSE_DECRYPTION_FAILED) from error
    try:
        body = plaintext.decode()
        encoding = "utf-8"
    except UnicodeDecodeError:
        body = base64.b64encode(plaintext).decode("ascii")
        encoding = "base64"
    await _audit_raw_view(
        session,
        call_id=call_id,
        actor_id=actor_id,
        result=audit_service.AUDIT_RESULT_SUCCESS,
        detail=f"response_sequence={raw.response_sequence}",
    )
    headers = raw.response_headers
    content_type = headers.get("content-type")
    return DecryptedRawResponseView(
        body=body,
        encoding=encoding,
        content_type=content_type if isinstance(content_type, str) else None,
        http_status=raw.http_status,
        response_sequence=raw.response_sequence,
        created_at=raw.created_at,
        expires_at=raw.expires_at,
    )


async def _audit_raw_view(
    session: AsyncSession,
    *,
    call_id: uuid.UUID,
    actor_id: uuid.UUID,
    result: str,
    detail: str,
) -> None:
    audit_service.record_event(
        session,
        actor_id=actor_id,
        action=RAW_RESPONSE_VIEW_ACTION,
        target_type="llm_call_record",
        target_id=str(call_id),
        result=result,
        detail=detail,
    )
    await session.commit()


def encode_cursor(created_at: datetime, call_id: uuid.UUID) -> str:
    raw = f"{created_at.astimezone(UTC).isoformat()}|{call_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.b64decode(padded, altchars=b"-_", validate=True).decode()
        raw_datetime, raw_id = raw.split("|", maxsplit=1)
        created_at = _aware_datetime(raw_datetime)
        return created_at, uuid.UUID(raw_id)
    except (ValueError, UnicodeDecodeError, binascii.Error) as error:
        message = "invalid_llm_call_cursor"
        raise InvalidLlmCallCursorError(message) from error


def _aware_datetime(raw: str) -> datetime:
    created_at = datetime.fromisoformat(raw)
    if created_at.tzinfo is None:
        message = "cursor datetime must include a timezone"
        raise ValueError(message)
    return created_at


def _outcome_view(event: LlmCallOutcomeEvent) -> LlmCallOutcomeView:
    return LlmCallOutcomeView(
        sequence_number=event.sequence_number,
        outcome=event.outcome,
        category=event.category,
        provider_request_id=event.provider_request_id,
        actual_model=event.actual_model,
        actual_provider=event.actual_provider,
        http_status=event.http_status,
        duration_ms=event.duration_ms,
        created_at=event.created_at,
    )


def _metadata_view(event: LlmCallMetadataEvent) -> LlmCallMetadataView:
    return LlmCallMetadataView(
        sequence_number=event.sequence_number,
        status=event.status,
        generation_id=event.generation_id,
        actual_model=event.actual_model,
        actual_provider=event.actual_provider,
        prompt_tokens=event.prompt_tokens,
        completion_tokens=event.completion_tokens,
        total_tokens=event.total_tokens,
        cost=event.cost,
        source=event.source,
        next_retry_at=event.next_retry_at,
        error_category=event.error_category,
        created_at=event.created_at,
    )
