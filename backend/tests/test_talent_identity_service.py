"""Unit tests for the pure local-talent identity decisions."""

import uuid
from datetime import UTC, datetime

from relationship_network_api.fake_search_base import SEEDED_PERSON_ID, SEEDED_PERSONS
from relationship_network_api.models import LocalTalent
from relationship_network_api.talent_identity_service import (
    CANONICAL_ID_KIND,
    SOURCE_ID_KIND,
    _availability_after_absence,
    _availability_after_found,
    _external_ids_for,
    _mapping_entries,
    _pick_survivor,
)


def test_mapping_entries_canonical_id_then_source_ids() -> None:
    person = SEEDED_PERSONS[SEEDED_PERSON_ID]
    entries = _mapping_entries(person)
    assert entries[0] == (person.canonical_person_id, CANONICAL_ID_KIND)
    assert entries[1:] == [
        ("src-openalex-001", SOURCE_ID_KIND),
        ("src-orcid-001", SOURCE_ID_KIND),
    ]


def test_external_ids_for_is_sorted_and_deduplicated() -> None:
    person = SEEDED_PERSONS[SEEDED_PERSON_ID]
    assert _external_ids_for(person) == sorted(
        {person.canonical_person_id, "src-openalex-001", "src-orcid-001"}
    )


def test_pick_survivor_chooses_earliest_created_at() -> None:
    older = LocalTalent(id=uuid.uuid4(), created_at=datetime(2024, 1, 1, tzinfo=UTC))
    newer = LocalTalent(id=uuid.uuid4(), created_at=datetime(2024, 2, 1, tzinfo=UTC))
    assert _pick_survivor([newer, older]) is older


def test_pick_survivor_breaks_ties_by_id() -> None:
    created_at = datetime(2024, 1, 1, tzinfo=UTC)
    first = LocalTalent(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        created_at=created_at,
    )
    second = LocalTalent(
        id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        created_at=created_at,
    )
    assert _pick_survivor([second, first]) is first


def test_availability_after_found_keeps_available_without_event() -> None:
    assert _availability_after_found("available") == ("available", None)


def test_availability_after_found_recovers_with_marked_available_event() -> None:
    assert _availability_after_found("temporarily_unavailable") == (
        "available",
        "marked_available",
    )


def test_availability_after_absence_marks_unavailable() -> None:
    assert _availability_after_absence("available") == (
        "temporarily_unavailable",
        "marked_unavailable",
    )


def test_availability_after_absence_is_noop_when_already_unavailable() -> None:
    assert _availability_after_absence("temporarily_unavailable") is None
