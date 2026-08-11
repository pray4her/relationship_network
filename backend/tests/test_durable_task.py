"""Tests for scope-neutral durable-task timing and SSE helpers."""

from __future__ import annotations

import json
import secrets

import pytest

from relationship_network_api import durable_task


def test_lease_covers_request_timeout_and_finishing_margin() -> None:
    assert durable_task.lease_seconds_for_timeout(300) == 360
    assert durable_task.lease_seconds_for_timeout(1) == durable_task.MINIMUM_LEASE_SECONDS


def test_retry_backoff_is_exponential_capped_and_jittered(monkeypatch: pytest.MonkeyPatch) -> None:
    def fixed_jitter(_upper: int) -> int:
        return 1

    monkeypatch.setattr(secrets, "randbelow", fixed_jitter)

    assert durable_task.retry_delay_seconds(1) == 3
    assert durable_task.retry_delay_seconds(4) == 17
    assert durable_task.retry_delay_seconds(20) == 31


@pytest.mark.parametrize(("value", "expected"), [(None, 0), ("0", 0), ("17", 17)])
def test_last_event_id_accepts_only_non_negative_integers(
    value: str | None,
    expected: int,
) -> None:
    assert durable_task.parse_last_event_id(value) == expected


@pytest.mark.parametrize("value", ["-1", "1.5", "not-a-sequence"])
def test_last_event_id_rejects_invalid_cursors(value: str) -> None:
    with pytest.raises(ValueError, match=r".+"):
        _ = durable_task.parse_last_event_id(value)


def test_sse_event_is_compact_utf8_and_heartbeat_is_not_persisted_data() -> None:
    encoded = durable_task.encode_sse_event(
        sequence_number=3,
        event_type="retry_scheduled",
        data={"status": "等待重试", "retryable": True},
    )

    assert encoded.startswith("id: 3\nevent: retry_scheduled\ndata: ")
    payload = encoded.split("data: ", maxsplit=1)[1].strip()
    assert json.loads(payload) == {"status": "等待重试", "retryable": True}
    assert "\\u" not in payload
    assert durable_task.encode_sse_heartbeat() == ": heartbeat\n\n"
