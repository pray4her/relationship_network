"""Local talent master identity: get-or-create, dedup, merge, and availability.

The sync path is the sole writer of the shared local talent master. Every
operation resolves identity through the external identifier mapping so that
repeated syncs of the same canonical person and search-base merges collapse
onto one stable local talent ID.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, final

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from relationship_network_api.models import (
    TALENT_AVAILABILITY_AVAILABLE,
    TALENT_AVAILABILITY_TEMPORARILY_UNAVAILABLE,
    ChineseIdentity,
    LocalTalent,
    TalentAvailability,
    TalentExternalId,
    TalentExternalIdKind,
    TalentIdentityEvent,
    TalentIdentityEventType,
)
from relationship_network_api.search_base_contract import (
    CanonicalPersonFields,
    PersonDetailFound,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from relationship_network_api.search_base import SearchBaseAdapter

CANONICAL_ID_KIND: TalentExternalIdKind = "canonical_person_id"
SOURCE_ID_KIND: TalentExternalIdKind = "source_id"
TALENT_NOT_FOUND_DETAIL: Final = "talent_not_found"


@final
class TalentNotFoundError(Exception):
    """Raised when a local talent ID does not resolve to a record."""

    def __init__(self, local_talent_id: uuid.UUID) -> None:
        super().__init__(f"local talent not found: {local_talent_id}")
        self.local_talent_id = local_talent_id


@final
@dataclass(frozen=True)
class LocalTalentView:
    """Latest known header snapshot plus source tracking for one local talent."""

    id: uuid.UUID
    canonical_person_id: str
    display_name: str
    current_affiliation: str
    country: str
    chinese_identity: ChineseIdentity
    h_index: int
    total_citations: int
    qs_top200_rank: int | None
    world_top500_rank: int | None
    has_contact: bool | None
    data_version: str
    availability: TalentAvailability
    last_synced_at: datetime
    historical_source_ids: tuple[str, ...]


def _availability_after_found(
    current: TalentAvailability,
) -> tuple[TalentAvailability, TalentIdentityEventType | None]:
    if current == TALENT_AVAILABILITY_TEMPORARILY_UNAVAILABLE:
        return (TALENT_AVAILABILITY_AVAILABLE, "marked_available")
    return (TALENT_AVAILABILITY_AVAILABLE, None)


def _availability_after_absence(
    current: TalentAvailability,
) -> tuple[TalentAvailability, TalentIdentityEventType] | None:
    if current == TALENT_AVAILABILITY_TEMPORARILY_UNAVAILABLE:
        return None
    return (TALENT_AVAILABILITY_TEMPORARILY_UNAVAILABLE, "marked_unavailable")


async def get_talent(
    session: AsyncSession,
    *,
    local_talent_id: uuid.UUID,
) -> LocalTalentView:
    """Read one local talent by its stable local ID."""
    talent = (
        await session.execute(select(LocalTalent).where(LocalTalent.id == local_talent_id))
    ).scalar_one_or_none()
    if talent is None:
        raise TalentNotFoundError(local_talent_id)
    return await _to_view(session, talent)


async def sync_person(
    session: AsyncSession,
    adapter: SearchBaseAdapter,
    canonical_person_id: str,
    *,
    request_id: str | None = None,
) -> LocalTalentView | None:
    """Re-sync one canonical person, resolving identity and availability.

    A ``found`` result upserts the latest header snapshot and marks the local
    talent available; a ``current_absence`` result marks it temporarily
    unavailable while freezing its fields.
    """
    result = await adapter.get_person(canonical_person_id, request_id=request_id)
    if isinstance(result, PersonDetailFound):
        return await _upsert_from_person(session, result.person, result.data_version)
    return await _mark_unavailable(session, canonical_person_id, result.data_version)


async def upsert_person(
    session: AsyncSession,
    person: CanonicalPersonFields,
    data_version: str,
) -> LocalTalentView:
    """Get-or-create one local talent from already-fetched person fields.

    The natural-language search run already holds the canonical person fields
    from a search hit, so it materializes the local talent here without a
    second detail read against the search base.
    """
    return await _upsert_from_person(session, person, data_version)


async def _upsert_from_person(
    session: AsyncSession,
    person: CanonicalPersonFields,
    data_version: str,
) -> LocalTalentView:
    """Get-or-create (with merge) one local talent from a canonical person.

    External identifiers are the reconciliation key: if they map to zero, one,
    or several local talents, this creates, refreshes, or merges accordingly.
    A unique violation on the mapping is retried by re-reading the winner so
    concurrent syncs serialize onto one row.
    """
    external_ids = _external_ids_for(person)
    try:
        existing = await _resolve_existing(session, external_ids)
        if not existing:
            talent = await _create(session, person, data_version)
        elif len(existing) == 1:
            talent = await _refresh(session, existing[0], person, data_version)
        else:
            talent = await _merge(session, existing, person, data_version)
        await session.commit()
        return await _to_view(session, talent)
    except IntegrityError:
        await session.rollback()
        existing = await _resolve_existing(session, external_ids)
        if not existing:
            raise
        if len(existing) == 1:
            return await _to_view(session, existing[0])
        talent = await _merge(session, existing, person, data_version)
        await session.commit()
        return await _to_view(session, talent)


async def _mark_unavailable(
    session: AsyncSession,
    canonical_person_id: str,
    data_version: str,
) -> LocalTalentView | None:
    """Mark an existing local talent temporarily unavailable on current absence."""
    talent = await _find_by_external_id(session, canonical_person_id)
    if talent is None:
        return None
    transition = _availability_after_absence(talent.availability)
    if transition is None:
        return None
    availability, event_type = transition
    talent.availability = availability
    talent.data_version = data_version
    talent.last_synced_at = datetime.now(UTC)
    await _add_event(
        session,
        event_type,
        talent.id,
        data_version,
        external_ids=[canonical_person_id],
    )
    await session.commit()
    return await _to_view(session, talent)


async def _create(
    session: AsyncSession,
    person: CanonicalPersonFields,
    data_version: str,
) -> LocalTalent:
    talent = LocalTalent(
        canonical_person_id=person.canonical_person_id,
        display_name=person.display_name,
        current_affiliation=person.current_affiliation,
        country=person.country,
        chinese_identity=person.chinese_identity,
        h_index=person.h_index,
        total_citations=person.total_citations,
        qs_top200_rank=person.qs_top200_rank,
        world_top500_rank=person.world_top500_rank,
        has_contact=person.has_contact,
        data_version=data_version,
        availability=TALENT_AVAILABILITY_AVAILABLE,
        last_synced_at=datetime.now(UTC),
    )
    session.add(talent)
    await session.flush()
    await _add_missing_mappings(session, talent.id, person)
    await _add_event(
        session,
        "created",
        talent.id,
        data_version,
        external_ids=_external_ids_for(person),
    )
    return talent


async def _refresh(
    session: AsyncSession,
    talent: LocalTalent,
    person: CanonicalPersonFields,
    data_version: str,
) -> LocalTalent:
    availability, event_type = _availability_after_found(talent.availability)
    _apply_snapshot(talent, person, data_version)
    talent.availability = availability
    await _add_missing_mappings(session, talent.id, person)
    if event_type is not None:
        await _add_event(
            session,
            event_type,
            talent.id,
            data_version,
            external_ids=_external_ids_for(person),
        )
    return talent


async def _merge(
    session: AsyncSession,
    talents: list[LocalTalent],
    person: CanonicalPersonFields,
    data_version: str,
) -> LocalTalent:
    survivor = _pick_survivor(talents)
    losers = [talent for talent in talents if talent.id != survivor.id]
    for loser in losers:
        _ = await session.execute(
            update(TalentExternalId)
            .where(TalentExternalId.local_talent_id == loser.id)
            .values(local_talent_id=survivor.id)
        )
        await session.delete(loser)
    _apply_snapshot(survivor, person, data_version)
    survivor.availability = TALENT_AVAILABILITY_AVAILABLE
    await _add_missing_mappings(session, survivor.id, person)
    await _add_event(
        session,
        "merged",
        survivor.id,
        data_version,
        external_ids=_external_ids_for(person),
        merged_from_ids=[str(loser.id) for loser in losers],
    )
    return survivor


async def _resolve_existing(
    session: AsyncSession,
    external_ids: list[str],
) -> list[LocalTalent]:
    talent_ids = set(
        (
            await session.execute(
                select(TalentExternalId.local_talent_id).where(
                    TalentExternalId.external_id.in_(external_ids)
                )
            )
        )
        .scalars()
        .all()
    )
    if not talent_ids:
        return []
    return list(
        (await session.execute(select(LocalTalent).where(LocalTalent.id.in_(talent_ids))))
        .scalars()
        .all()
    )


async def _find_by_external_id(
    session: AsyncSession,
    external_id: str,
) -> LocalTalent | None:
    local_talent_id = (
        await session.execute(
            select(TalentExternalId.local_talent_id).where(
                TalentExternalId.external_id == external_id
            )
        )
    ).scalar_one_or_none()
    if local_talent_id is None:
        return None
    return (
        await session.execute(select(LocalTalent).where(LocalTalent.id == local_talent_id))
    ).scalar_one_or_none()


def _apply_snapshot(
    talent: LocalTalent,
    person: CanonicalPersonFields,
    data_version: str,
) -> None:
    talent.canonical_person_id = person.canonical_person_id
    talent.display_name = person.display_name
    talent.current_affiliation = person.current_affiliation
    talent.country = person.country
    talent.chinese_identity = person.chinese_identity
    talent.h_index = person.h_index
    talent.total_citations = person.total_citations
    talent.qs_top200_rank = person.qs_top200_rank
    talent.world_top500_rank = person.world_top500_rank
    talent.has_contact = person.has_contact
    talent.data_version = data_version
    talent.last_synced_at = datetime.now(UTC)


async def _add_missing_mappings(
    session: AsyncSession,
    local_talent_id: uuid.UUID,
    person: CanonicalPersonFields,
) -> None:
    added: set[str] = set(
        (
            await session.execute(
                select(TalentExternalId.external_id).where(
                    TalentExternalId.local_talent_id == local_talent_id
                )
            )
        )
        .scalars()
        .all()
    )
    for external_id, kind in _mapping_entries(person):
        if external_id not in added:
            added.add(external_id)
            session.add(
                TalentExternalId(
                    external_id=external_id,
                    kind=kind,
                    local_talent_id=local_talent_id,
                )
            )


async def _add_event(  # noqa: PLR0913
    session: AsyncSession,
    event_type: TalentIdentityEventType,
    local_talent_id: uuid.UUID,
    data_version: str,
    *,
    external_ids: list[str],
    merged_from_ids: list[str] | None = None,
) -> None:
    """Append an identity event without RETURNING so the sync role needs no read grant."""
    _ = await session.execute(
        insert(TalentIdentityEvent)
        .inline()
        .values(
            id=uuid.uuid4(),
            event_type=event_type,
            local_talent_id=local_talent_id,
            data_version=data_version,
            external_ids=external_ids,
            merged_from_ids=merged_from_ids,
        )
    )


async def _to_view(session: AsyncSession, talent: LocalTalent) -> LocalTalentView:
    source_ids = tuple(
        sorted(
            (
                await session.execute(
                    select(TalentExternalId.external_id).where(
                        TalentExternalId.local_talent_id == talent.id,
                        TalentExternalId.kind == SOURCE_ID_KIND,
                    )
                )
            )
            .scalars()
            .all()
        )
    )
    return LocalTalentView(
        id=talent.id,
        canonical_person_id=talent.canonical_person_id,
        display_name=talent.display_name,
        current_affiliation=talent.current_affiliation,
        country=talent.country,
        chinese_identity=talent.chinese_identity,
        h_index=talent.h_index,
        total_citations=talent.total_citations,
        qs_top200_rank=talent.qs_top200_rank,
        world_top500_rank=talent.world_top500_rank,
        has_contact=talent.has_contact,
        data_version=talent.data_version,
        availability=talent.availability,
        last_synced_at=talent.last_synced_at,
        historical_source_ids=source_ids,
    )


def _pick_survivor(talents: list[LocalTalent]) -> LocalTalent:
    """Deterministically pick the earliest local talent as the merge survivor."""
    return min(talents, key=lambda talent: (talent.created_at, str(talent.id)))


def _external_ids_for(person: CanonicalPersonFields) -> list[str]:
    return sorted({external_id for external_id, _kind in _mapping_entries(person)})


def _mapping_entries(
    person: CanonicalPersonFields,
) -> list[tuple[str, TalentExternalIdKind]]:
    entries: list[tuple[str, TalentExternalIdKind]] = [
        (person.canonical_person_id, CANONICAL_ID_KIND)
    ]
    entries.extend((source_id, SOURCE_ID_KIND) for source_id in person.historical_source_ids)
    return entries
