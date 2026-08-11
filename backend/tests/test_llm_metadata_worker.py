from datetime import UTC, datetime, timedelta

import pytest

from relationship_network_api.llm_metadata_worker import next_metadata_retry_at


@pytest.mark.parametrize(
    ("sequence_number", "expected_delay"),
    [(1, 120), (2, 600), (3, 3600), (4, 21600)],
)
def test_generation_metadata_uses_the_persisted_retry_schedule(
    sequence_number: int,
    expected_delay: int,
) -> None:
    created_at = datetime(2026, 8, 11, tzinfo=UTC)
    now = created_at + timedelta(minutes=1)

    assert next_metadata_retry_at(
        call_created_at=created_at,
        current_sequence_number=sequence_number,
        now=now,
    ) == now + timedelta(seconds=expected_delay)


def test_generation_metadata_schedules_the_final_check_at_24_hours() -> None:
    created_at = datetime(2026, 8, 11, tzinfo=UTC)

    assert next_metadata_retry_at(
        call_created_at=created_at,
        current_sequence_number=5,
        now=created_at + timedelta(hours=7),
    ) == created_at + timedelta(hours=24)
    assert (
        next_metadata_retry_at(
            call_created_at=created_at,
            current_sequence_number=6,
            now=created_at + timedelta(hours=24),
        )
        is None
    )
