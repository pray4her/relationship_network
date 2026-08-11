from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final

from sqlalchemy import insert, select

from relationship_network_api import tenant_context
from relationship_network_api.config import (
    AppSettings,
    PlatformLlmSettings,
    load_app_settings,
    load_platform_llm_settings,
)
from relationship_network_api.db import (
    PLATFORM_WORKER_DATABASE_ROLE,
    create_engine_from_settings,
    create_session_factory,
)
from relationship_network_api.llm_call_audit_service import (
    LLM_METADATA_OUTBOX_TOPIC,
    acquire_call_transaction_lock,
)
from relationship_network_api.models import (
    LlmCallMetadataEvent,
    LlmCallRecord,
    PlatformOutboxEvent,
    TenantOutboxEvent,
)
from relationship_network_api.openrouter import (
    OpenRouterAdapter,
    OpenRouterAdapterError,
    OpenRouterClientConfig,
    OpenRouterGenerationMetadata,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_RETRY_DELAYS_SECONDS: Final = (120, 600, 3600, 21600)
_FINAL_UNAVAILABLE_AFTER: Final = timedelta(hours=24)


def next_metadata_retry_at(
    *,
    call_created_at: datetime,
    current_sequence_number: int,
    now: datetime,
) -> datetime | None:
    """Return the next durable retry time, or None once the 24-hour deadline passes."""
    if now - call_created_at >= _FINAL_UNAVAILABLE_AFTER:
        return None
    retry_index = current_sequence_number - 1
    if retry_index < len(_RETRY_DELAYS_SECONDS):
        return now + timedelta(seconds=_RETRY_DELAYS_SECONDS[retry_index])
    return call_created_at + _FINAL_UNAVAILABLE_AFTER


async def fetch_platform_call_metadata(
    call_id: uuid.UUID,
    *,
    settings: PlatformLlmSettings | None = None,
) -> None:
    """Fetch delayed OpenRouter generation facts without touching business state."""
    resolved = settings or load_platform_llm_settings()
    engine = create_engine_from_settings(resolved, database_role=PLATFORM_WORKER_DATABASE_ROLE)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            current = await _load_pending(session, call_id, tenant_id=None)
        if current is None:
            return
        call, metadata = current
        if resolved.openrouter_api_key is None or metadata.generation_id is None:
            await _append_unavailable(
                factory, call_id, "generation_metadata_not_configured", tenant_id=None
            )
            return
        if metadata.sequence_number >= len(_RETRY_DELAYS_SECONDS) + 2:
            await _append_unavailable(
                factory, call_id, "metadata_deadline_exceeded", tenant_id=None
            )
            return
        adapter = OpenRouterAdapter(
            OpenRouterClientConfig(
                api_key=resolved.openrouter_api_key.get_secret_value(),
                base_url=resolved.openrouter_base_url,
                site_url=resolved.openrouter_site_url,
                site_name=resolved.openrouter_site_name,
            )
        )
        try:
            result = await adapter.fetch_generation(metadata.generation_id)
        except OpenRouterAdapterError as error:
            await _append_retry_or_unavailable(
                factory, call, metadata, error.category, tenant_id=None
            )
        else:
            await _append_available(factory, call_id, result, tenant_id=None)
    finally:
        await engine.dispose()


async def _load_pending(
    session: AsyncSession,
    call_id: uuid.UUID,
    *,
    tenant_id: uuid.UUID | None,
) -> tuple[LlmCallRecord, LlmCallMetadataEvent] | None:
    if tenant_id is not None:
        await tenant_context.set_tenant_context(session, tenant_id)
    scope = "platform" if tenant_id is None else "tenant"
    row = (
        await session.execute(
            select(LlmCallRecord, LlmCallMetadataEvent)
            .join(LlmCallMetadataEvent, LlmCallMetadataEvent.call_id == LlmCallRecord.id)
            .where(LlmCallRecord.id == call_id, LlmCallRecord.scope == scope)
            .order_by(LlmCallMetadataEvent.sequence_number.desc())
            .limit(1)
        )
    ).one_or_none()
    if row is None or row.LlmCallMetadataEvent.status != "retry_scheduled":
        return None
    return row.LlmCallRecord, row.LlmCallMetadataEvent


async def _append_available(
    factory: async_sessionmaker[AsyncSession],
    call_id: uuid.UUID,
    result: OpenRouterGenerationMetadata,
    *,
    tenant_id: uuid.UUID | None,
) -> None:
    async with factory() as session, session.begin():
        call, current = await _locked_pending(session, call_id, tenant_id=tenant_id)
        if call is None or current is None:
            return
        session.add(
            LlmCallMetadataEvent(
                call_id=call.id,
                sequence_number=current.sequence_number + 1,
                scope=call.scope,
                tenant_id=call.tenant_id,
                status="available",
                generation_id=result.generation_id,
                actual_model=result.actual_model,
                actual_provider=result.actual_provider,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                total_tokens=result.total_tokens,
                cost=result.cost,
                source="generation_api",
                next_retry_at=None,
                error_category="",
            )
        )


async def _append_retry_or_unavailable(
    factory: async_sessionmaker[AsyncSession],
    call: LlmCallRecord,
    current: LlmCallMetadataEvent,
    category: str,
    *,
    tenant_id: uuid.UUID | None,
) -> None:
    now = datetime.now(UTC)
    next_retry_at = next_metadata_retry_at(
        call_created_at=call.created_at,
        current_sequence_number=current.sequence_number,
        now=now,
    )
    if next_retry_at is None:
        await _append_unavailable(
            factory,
            call.id,
            "metadata_deadline_exceeded",
            tenant_id=tenant_id,
        )
        return
    async with factory() as session, session.begin():
        locked_call, locked_current = await _locked_pending(session, call.id, tenant_id=tenant_id)
        if locked_call is None or locked_current is None:
            return
        session.add(
            LlmCallMetadataEvent(
                call_id=locked_call.id,
                sequence_number=locked_current.sequence_number + 1,
                scope=locked_call.scope,
                tenant_id=locked_call.tenant_id,
                status="retry_scheduled",
                generation_id=locked_current.generation_id,
                actual_model=locked_current.actual_model,
                actual_provider=locked_current.actual_provider,
                prompt_tokens=None,
                completion_tokens=None,
                total_tokens=None,
                cost=None,
                source="generation_api",
                next_retry_at=next_retry_at,
                error_category=category,
            )
        )
        if tenant_id is None:
            _ = await session.execute(
                insert(PlatformOutboxEvent)
                .inline()
                .values(
                    id=uuid.uuid4(),
                    topic=LLM_METADATA_OUTBOX_TOPIC,
                    aggregate_id=locked_call.id,
                    available_at=next_retry_at,
                )
            )
        else:
            task_id = locked_call.job_requirement_parsing_task_id
            if task_id is None:
                message = "tenant metadata retry requires a parsing task"
                raise RuntimeError(message)
            session.add(
                TenantOutboxEvent(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    topic=LLM_METADATA_OUTBOX_TOPIC,
                    aggregate_id=locked_call.id,
                    job_requirement_parsing_task_id=task_id,
                    available_at=next_retry_at,
                )
            )


async def _append_unavailable(
    factory: async_sessionmaker[AsyncSession],
    call_id: uuid.UUID,
    category: str,
    *,
    tenant_id: uuid.UUID | None,
) -> None:
    async with factory() as session, session.begin():
        call, current = await _locked_pending(session, call_id, tenant_id=tenant_id)
        if call is None or current is None:
            return
        session.add(
            LlmCallMetadataEvent(
                call_id=call.id,
                sequence_number=current.sequence_number + 1,
                scope=call.scope,
                tenant_id=call.tenant_id,
                status="unavailable",
                generation_id=current.generation_id,
                actual_model=current.actual_model,
                actual_provider=current.actual_provider,
                prompt_tokens=None,
                completion_tokens=None,
                total_tokens=None,
                cost=None,
                source="generation_api",
                next_retry_at=None,
                error_category=category,
            )
        )


async def _locked_pending(
    session: AsyncSession,
    call_id: uuid.UUID,
    *,
    tenant_id: uuid.UUID | None,
) -> tuple[LlmCallRecord | None, LlmCallMetadataEvent | None]:
    if tenant_id is not None:
        await tenant_context.set_tenant_context(session, tenant_id)
    await acquire_call_transaction_lock(session, call_id)
    call = (
        await session.execute(select(LlmCallRecord).where(LlmCallRecord.id == call_id))
    ).scalar_one_or_none()
    if call is None:
        return None, None
    current = (
        await session.execute(
            select(LlmCallMetadataEvent)
            .where(LlmCallMetadataEvent.call_id == call_id)
            .order_by(LlmCallMetadataEvent.sequence_number.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if current is None or current.status != "retry_scheduled":
        return call, None
    return call, current


async def fetch_tenant_call_metadata(
    tenant_id: uuid.UUID,
    call_id: uuid.UUID,
    *,
    settings: AppSettings | None = None,
) -> None:
    """Fetch delayed facts for a tenant call under the ordinary app role and RLS."""
    resolved = settings or load_app_settings()
    engine = create_engine_from_settings(resolved)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            current = await _load_pending(session, call_id, tenant_id=tenant_id)
        if current is None:
            return
        call, metadata = current
        if resolved.openrouter_api_key is None or metadata.generation_id is None:
            await _append_unavailable(
                factory,
                call_id,
                "generation_metadata_not_configured",
                tenant_id=tenant_id,
            )
            return
        adapter = OpenRouterAdapter(
            OpenRouterClientConfig(
                api_key=resolved.openrouter_api_key.get_secret_value(),
                base_url=resolved.openrouter_base_url,
                site_url=resolved.openrouter_site_url,
                site_name=resolved.openrouter_site_name,
            )
        )
        try:
            result = await adapter.fetch_generation(metadata.generation_id)
        except OpenRouterAdapterError as error:
            await _append_retry_or_unavailable(
                factory,
                call,
                metadata,
                error.category,
                tenant_id=tenant_id,
            )
        else:
            await _append_available(factory, call_id, result, tenant_id=tenant_id)
    finally:
        await engine.dispose()
