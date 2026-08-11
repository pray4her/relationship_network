from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, final

import anyio
from anyio import to_thread
from kombu.exceptions import OperationalError
from sqlalchemy import text

from relationship_network_api.celery_app import create_celery_app
from relationship_network_api.config import WorkerSettings, load_database_settings
from relationship_network_api.db import (
    OUTBOX_DISPATCHER_DATABASE_ROLE,
    create_engine_from_settings,
    create_session_factory,
)
from relationship_network_api.job_requirement_service import (
    OUTBOX_TOPIC as REQUIREMENT_OUTBOX_TOPIC,
)
from relationship_network_api.llm_call_audit_service import LLM_METADATA_OUTBOX_TOPIC
from relationship_network_api.llm_configuration_service import OUTBOX_TOPIC
from relationship_network_api.tasks import (
    FETCH_LLM_CALL_METADATA_TASK_NAME,
    FETCH_TENANT_LLM_CALL_METADATA_TASK_NAME,
    PROCESS_JOB_REQUIREMENT_TASK_NAME,
    PROCESS_LLM_CONFIGURATION_ATTEMPT_TASK_NAME,
)

if TYPE_CHECKING:
    from celery import Celery
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_BATCH_SIZE: Final = 25
_CLAIM_LEASE_SECONDS: Final = 30
_IDLE_SECONDS: Final = 1.0
_CLAIM_SQL: Final = "SELECT event_id, topic, aggregate_id FROM claim_platform_outbox_batch(:claimant, :batch_size, :lease_seconds)"  # noqa: E501
_CLAIM_TENANT_SQL: Final = (
    "SELECT event_id, tenant_id, topic, aggregate_id, task_id "
    "FROM claim_tenant_outbox_batch(:claimant, :batch_size, :lease_seconds)"
)


@final
@dataclass(frozen=True)
class ClaimedOutboxEvent:
    id: uuid.UUID
    topic: str
    aggregate_id: uuid.UUID


@final
@dataclass(frozen=True)
class ClaimedTenantOutboxEvent:
    id: uuid.UUID
    tenant_id: uuid.UUID
    topic: str
    aggregate_id: uuid.UUID
    task_id: uuid.UUID


async def claim_batch(
    session: AsyncSession,
    *,
    claimant: uuid.UUID,
) -> list[ClaimedOutboxEvent]:
    rows = (
        await session.execute(
            text(_CLAIM_SQL),
            {
                "batch_size": _BATCH_SIZE,
                "claimant": claimant,
                "lease_seconds": _CLAIM_LEASE_SECONDS,
            },
        )
    ).all()
    await session.commit()
    return [
        ClaimedOutboxEvent(id=row.event_id, topic=row.topic, aggregate_id=row.aggregate_id)
        for row in rows
    ]


async def claim_tenant_batch(
    session: AsyncSession,
    *,
    claimant: uuid.UUID,
) -> list[ClaimedTenantOutboxEvent]:
    rows = (
        await session.execute(
            text(_CLAIM_TENANT_SQL),
            {
                "batch_size": _BATCH_SIZE,
                "claimant": claimant,
                "lease_seconds": _CLAIM_LEASE_SECONDS,
            },
        )
    ).all()
    await session.commit()
    return [
        ClaimedTenantOutboxEvent(
            id=row.event_id,
            tenant_id=row.tenant_id,
            topic=row.topic,
            aggregate_id=row.aggregate_id,
            task_id=row.task_id,
        )
        for row in rows
    ]


async def acknowledge(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    event_id: uuid.UUID,
    claimant: uuid.UUID,
) -> None:
    async with session_factory() as session:
        _ = await session.execute(
            text("SELECT acknowledge_platform_outbox(:event_id, :claimant)"),
            {"claimant": claimant, "event_id": event_id},
        )
        await session.commit()


async def release(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    event_id: uuid.UUID,
    claimant: uuid.UUID,
    error_text: str,
) -> None:
    async with session_factory() as session:
        _ = await session.execute(
            text("SELECT release_platform_outbox_claim(:event_id, :claimant, :error_text)"),
            {"claimant": claimant, "error_text": error_text, "event_id": event_id},
        )
        await session.commit()


async def acknowledge_tenant(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    event_id: uuid.UUID,
    claimant: uuid.UUID,
) -> None:
    async with session_factory() as session:
        _ = await session.execute(
            text("SELECT acknowledge_tenant_outbox(:event_id, :claimant)"),
            {"claimant": claimant, "event_id": event_id},
        )
        await session.commit()


async def release_tenant(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    event_id: uuid.UUID,
    claimant: uuid.UUID,
    error_text: str,
) -> None:
    async with session_factory() as session:
        _ = await session.execute(
            text("SELECT release_tenant_outbox_claim(:event_id, :claimant, :error_text)"),
            {"claimant": claimant, "error_text": error_text, "event_id": event_id},
        )
        await session.commit()


async def dispatch_forever() -> None:  # noqa: C901, PLR0912
    database_settings = load_database_settings()
    engine = create_engine_from_settings(
        database_settings,
        database_role=OUTBOX_DISPATCHER_DATABASE_ROLE,
    )
    session_factory = create_session_factory(engine)
    celery = create_celery_app(WorkerSettings())
    claimant = uuid.uuid4()
    try:
        while True:
            async with session_factory() as session:
                events = await claim_batch(session, claimant=claimant)
            async with session_factory() as session:
                tenant_events = await claim_tenant_batch(session, claimant=claimant)
            for event in events:
                if event.topic not in {OUTBOX_TOPIC, LLM_METADATA_OUTBOX_TOPIC}:
                    await release(
                        session_factory,
                        event_id=event.id,
                        claimant=claimant,
                        error_text="unsupported platform Outbox topic",
                    )
                    continue
                try:
                    if event.topic == OUTBOX_TOPIC:
                        await to_thread.run_sync(_send_attempt, celery, event.aggregate_id)
                    else:
                        await to_thread.run_sync(_send_metadata, celery, event.aggregate_id)
                except (OSError, OperationalError) as error:
                    await release(
                        session_factory,
                        event_id=event.id,
                        claimant=claimant,
                        error_text=type(error).__name__,
                    )
                else:
                    await acknowledge(
                        session_factory,
                        event_id=event.id,
                        claimant=claimant,
                    )
            for event in tenant_events:
                if event.topic not in {REQUIREMENT_OUTBOX_TOPIC, LLM_METADATA_OUTBOX_TOPIC}:
                    await release_tenant(
                        session_factory,
                        event_id=event.id,
                        claimant=claimant,
                        error_text="unsupported tenant Outbox topic",
                    )
                    continue
                try:
                    if event.topic == REQUIREMENT_OUTBOX_TOPIC:
                        await to_thread.run_sync(_send_requirement_task, celery, event)
                    else:
                        await to_thread.run_sync(_send_tenant_metadata, celery, event)
                except (OSError, OperationalError) as error:
                    await release_tenant(
                        session_factory,
                        event_id=event.id,
                        claimant=claimant,
                        error_text=type(error).__name__,
                    )
                else:
                    await acknowledge_tenant(
                        session_factory,
                        event_id=event.id,
                        claimant=claimant,
                    )
            if not events and not tenant_events:
                await anyio.sleep(_IDLE_SECONDS)
    finally:
        await engine.dispose()


def _send_attempt(celery: Celery, attempt_id: uuid.UUID) -> None:
    _ = celery.send_task(
        PROCESS_LLM_CONFIGURATION_ATTEMPT_TASK_NAME,
        args=[str(attempt_id)],
        queue="platform",
    )


def _send_metadata(celery: Celery, call_id: uuid.UUID) -> None:
    _ = celery.send_task(
        FETCH_LLM_CALL_METADATA_TASK_NAME,
        args=[str(call_id)],
        queue="platform",
    )


def _send_requirement_task(celery: Celery, event: ClaimedTenantOutboxEvent) -> None:
    _ = celery.send_task(
        PROCESS_JOB_REQUIREMENT_TASK_NAME,
        args=[str(event.tenant_id), str(event.task_id)],
        queue="tenant",
    )


def _send_tenant_metadata(celery: Celery, event: ClaimedTenantOutboxEvent) -> None:
    _ = celery.send_task(
        FETCH_TENANT_LLM_CALL_METADATA_TASK_NAME,
        args=[str(event.tenant_id), str(event.aggregate_id)],
        queue="tenant",
    )


if __name__ == "__main__":
    anyio.run(dispatch_forever)
