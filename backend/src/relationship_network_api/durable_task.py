"""Scope-neutral primitives shared by persisted LLM task implementations."""

from __future__ import annotations

import json
import secrets
from typing import Final

HEARTBEAT_SECONDS: Final = 15
MAX_CONNECTION_SECONDS: Final = 60
POLL_SECONDS: Final = 1.0
MAX_EXTERNAL_CALLS: Final = 3
MAX_STRUCTURED_INVALID_CALLS: Final = 2
LEASE_FINISHING_MARGIN_SECONDS: Final = 60
MINIMUM_LEASE_SECONDS: Final = 90

SSE_RESPONSE_HEADERS: Final = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def lease_seconds_for_timeout(request_timeout_seconds: int) -> int:
    """Keep a lease valid for the configured request plus a bounded commit margin."""
    return max(
        MINIMUM_LEASE_SECONDS,
        request_timeout_seconds + LEASE_FINISHING_MARGIN_SECONDS,
        HEARTBEAT_SECONDS * 3,
    )


def retry_delay_seconds(request_number: int) -> int:
    """Return capped exponential backoff with a small shared jitter window."""
    exponential = min(2 ** max(request_number, 1), 30)
    return exponential + secrets.randbelow(2)


def parse_last_event_id(value: str | None) -> int:
    """Parse the SSE replay cursor and reject negative or malformed values."""
    sequence = 0 if value is None else int(value)
    if sequence < 0:
        raise ValueError(value)
    return sequence


def encode_sse_event(*, sequence_number: int, event_type: str, data: object) -> str:
    """Encode one compact, UTF-8-safe persisted SSE event."""
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"id: {sequence_number}\nevent: {event_type}\ndata: {payload}\n\n"


def encode_sse_heartbeat() -> str:
    """Encode a non-persisted SSE comment heartbeat."""
    return ": heartbeat\n\n"
