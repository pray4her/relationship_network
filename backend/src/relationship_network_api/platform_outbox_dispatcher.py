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
from relationship_network_api.llm_configuration_service import OUTBOX_TOPIC
from relationship_network_api.tasks import PROCESS_LLM_CONFIGURATION_ATTEMPT_TASK_NAME

if TYPE_CHECKING:
    from celery import Celery
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_BATCH_SIZE: Final = 25
_CLAIM_LEASE_SECONDS: Final = 30
_IDLE_SECONDS: Final = 1.0
_CLAIM_SQL: Final = "SELECT event_id, topic, aggregate_id FROM claim_platform_outbox_batch(:claimant, :batch_size, :lease_seconds)"  # noqa: E501


@final
@dataclass(frozen=True)
class ClaimedOutboxEvent:
    id: uuid.UUID
    topic: str
    aggregate_id: uuid.UUID


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


async def dispatch_forever() -> None:
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
            if not events:
                await anyio.sleep(_IDLE_SECONDS)
                continue
            for event in events:
                if event.topic != OUTBOX_TOPIC:
                    await release(
                        session_factory,
                        event_id=event.id,
                        claimant=claimant,
                        error_text="unsupported platform Outbox topic",
                    )
                    continue
                try:
                    await to_thread.run_sync(
                        _send_attempt,
                        celery,
                        event.aggregate_id,
                    )
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
    finally:
        await engine.dispose()


def _send_attempt(celery: Celery, attempt_id: uuid.UUID) -> None:
    _ = celery.send_task(
        PROCESS_LLM_CONFIGURATION_ATTEMPT_TASK_NAME,
        args=[str(attempt_id)],
        queue="platform",
    )


if __name__ == "__main__":
    anyio.run(dispatch_forever)
