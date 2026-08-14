"""Deterministic fake OpenRouter used by Compose, CI, and integration tests.

Scenario selection is primarily the request model ID. Successful payloads still
branch on the strict JSON Schema name so a seeded production model can probe
and generate without a real API key.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, cast, override

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

if TYPE_CHECKING:
    from starlette.types import Receive, Scope, Send

PROBE_SCHEMA_NAME: Final = "relationship_network_config_probe"
REQUIREMENT_SCHEMA_NAME: Final = "relationship_network_job_requirement"
SEARCH_INTERPRETATION_SCHEMA_NAME: Final = "relationship_network_search_interpretation"
FAKE_REQUEST_ID: Final = "fake-openrouter-request"
FAKE_PROVIDER: Final = "fake-zdr-provider"
DEFAULT_RESEARCH_TOPIC: Final = "人工智能"
DEFAULT_HANG_SECONDS: Final = 3600.0
DEFAULT_DELAY_SECONDS: Final = 3.0
DEFAULT_LATE_SECONDS: Final = 2.0
DEFAULT_GENERATION_DELAY_SECONDS: Final = 2.0
QUOTE_SLICE_CHARS: Final = 8
MIN_CONFLICT_SOURCES: Final = 2
HTTP_BAD_REQUEST: Final = 400
HTTP_FORBIDDEN: Final = 403
HTTP_NOT_FOUND: Final = 404
HTTP_TOO_MANY_REQUESTS: Final = 429
HTTP_SERVER_ERROR: Final = 500
REQUIRED_ROUTING: Final = {
    "data_collection": "deny",
    "require_parameters": True,
    "zdr": True,
}

MODEL_RATE_LIMITED: Final = "test/rate-limited"
MODEL_INVALID_STRUCTURE: Final = "test/invalid-structure"
MODEL_SERVER_ERROR: Final = "test/server-error"
MODEL_TIMEOUT: Final = "test/timeout"
MODEL_DISCONNECT: Final = "test/disconnect"
MODEL_LATE_RESPONSE: Final = "test/late-response"
MODEL_PROVIDER_DENIED: Final = "test/provider-denied"
MODEL_DELAYED_SUCCESS: Final = "test/delayed-success"
MODEL_DELAYED_GENERATION: Final = "test/delayed-generation"
MODEL_WITH_CONFLICTS: Final = "test/with-conflicts"
MODEL_SEARCH_INTERPRETATION_INVALID: Final = "test/search-interpretation-invalid"

app = FastAPI(title="Fake OpenRouter")
_generation_ready_at: dict[str, float] = {}


@dataclass
class FakeOpenRouterTiming:
    """Controllable delays so tests need not wait for production timeouts."""

    hang_seconds: float = DEFAULT_HANG_SECONDS
    delay_seconds: float = DEFAULT_DELAY_SECONDS
    late_seconds: float = DEFAULT_LATE_SECONDS
    generation_delay_seconds: float = DEFAULT_GENERATION_DELAY_SECONDS


timing = FakeOpenRouterTiming()


def _apply_env_timing() -> None:
    raw = os.environ.get("FAKE_OPENROUTER_DELAY_SECONDS", "").strip()
    if raw:
        timing.delay_seconds = float(raw)


_apply_env_timing()


def reset_fake_openrouter() -> None:
    """Restore timing and delayed-generation state between tests."""
    timing.hang_seconds = DEFAULT_HANG_SECONDS
    timing.delay_seconds = DEFAULT_DELAY_SECONDS
    timing.late_seconds = DEFAULT_LATE_SECONDS
    timing.generation_delay_seconds = DEFAULT_GENERATION_DELAY_SECONDS
    _generation_ready_at.clear()


class ImmediateDisconnect(Response):
    """Abort after the request body is read so clients observe a dropped connection."""

    @override
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        del scope, receive
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        message = "fake openrouter disconnect"
        raise ConnectionResetError(message)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(content={"status": "ok"})


@app.get("/api/v1/generation")
async def generation(id: str) -> JSONResponse:  # noqa: A002
    ready_at = _generation_ready_at.get(id)
    if ready_at is not None and time.monotonic() < ready_at:
        return JSONResponse(status_code=HTTP_NOT_FOUND, content={"error": "generation pending"})
    return JSONResponse(
        content={
            "data": {
                "id": id,
                "model": "test/success",
                "provider_name": FAKE_PROVIDER,
                "tokens_prompt": 12,
                "tokens_completion": 4,
                "total_cost": 0.000012,
            }
        }
    )


@app.post("/api/v1/chat/completions")
async def chat_completions(request: Request) -> Response:
    payload = cast("dict[str, object]", await request.json())
    routing_error = _routing_error(payload)
    if routing_error is not None:
        return routing_error
    model = str(payload.get("model", ""))
    return await _completion_for_model(model, payload)


def _routing_error(payload: dict[str, object]) -> JSONResponse | None:
    provider = payload.get("provider", {})
    response_format = payload.get("response_format", {})
    json_schema = (
        response_format.get("json_schema", {}) if isinstance(response_format, dict) else {}
    )
    if (
        payload.get("stream") is not False
        or "models" in payload
        or provider != REQUIRED_ROUTING
        or not isinstance(response_format, dict)
        or response_format.get("type") != "json_schema"
        or not isinstance(json_schema, dict)
        or json_schema.get("strict") is not True
    ):
        return JSONResponse(
            status_code=HTTP_BAD_REQUEST,
            content={"error": "required parameters missing"},
        )
    return None


async def _completion_for_model(model: str, payload: dict[str, object]) -> Response:
    if model == MODEL_TIMEOUT:
        await asyncio.sleep(timing.hang_seconds)
    elif model == MODEL_LATE_RESPONSE:
        await asyncio.sleep(timing.late_seconds)
    elif model == MODEL_DELAYED_SUCCESS:
        await asyncio.sleep(timing.delay_seconds)

    error_response = _error_response_for_model(model)
    if error_response is not None:
        return error_response
    content = (
        _invalid_content()
        if model == MODEL_INVALID_STRUCTURE
        else _content_for_schema(payload, model)
    )
    response = _success_response(model, content)
    if model == MODEL_DELAYED_GENERATION:
        _generation_ready_at[FAKE_REQUEST_ID] = time.monotonic() + timing.generation_delay_seconds
    return response


def _error_response_for_model(model: str) -> Response | None:
    if model == MODEL_DISCONNECT:
        return ImmediateDisconnect()
    if model == MODEL_PROVIDER_DENIED:
        return JSONResponse(
            status_code=HTTP_FORBIDDEN,
            content={"error": "privacy routing rejected: no zdr provider"},
        )
    if model == MODEL_RATE_LIMITED:
        return JSONResponse(
            status_code=HTTP_TOO_MANY_REQUESTS,
            headers={"Retry-After": "1"},
            content={"error": "rate limited"},
        )
    if model == MODEL_SERVER_ERROR:
        return JSONResponse(status_code=HTTP_SERVER_ERROR, content={"error": "upstream 5xx"})
    return None


def _schema_name(payload: dict[str, object]) -> str:
    response_format = payload.get("response_format", {})
    if not isinstance(response_format, dict):
        return ""
    json_schema = response_format.get("json_schema", {})
    if not isinstance(json_schema, dict):
        return ""
    schema_object = cast("dict[str, object]", json_schema)
    return str(schema_object.get("name", ""))


def _content_for_schema(payload: dict[str, object], model: str) -> str:
    name = _schema_name(payload)
    if model == MODEL_SEARCH_INTERPRETATION_INVALID:
        if name == REQUIREMENT_SCHEMA_NAME:
            result = build_requirement_result(_sources_from_payload(payload))
            return json.dumps(result, ensure_ascii=False)
        return _invalid_content()
    if name == REQUIREMENT_SCHEMA_NAME:
        result = build_requirement_result(
            _sources_from_payload(payload),
            with_conflicts=model == MODEL_WITH_CONFLICTS,
        )
        return json.dumps(result, ensure_ascii=False)
    if name == SEARCH_INTERPRETATION_SCHEMA_NAME:
        return json.dumps(build_search_interpretation_result(), ensure_ascii=False)
    return _invalid_content()


def _invalid_content() -> str:
    return json.dumps({"capability": "not-ok"})


def _success_response(model: str, content: str) -> JSONResponse:
    return JSONResponse(
        content={
            "choices": [{"message": {"content": content, "role": "assistant"}}],
            "id": FAKE_REQUEST_ID,
            "model": model,
            "provider": FAKE_PROVIDER,
        }
    )


def _sources_from_payload(payload: dict[str, object]) -> list[dict[str, str]]:
    messages = payload.get("messages")
    last = messages[-1] if isinstance(messages, list) and messages else None
    raw_content = last.get("content") if isinstance(last, dict) else None
    parsed: object = None
    if isinstance(raw_content, str):
        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError:
            parsed = None
    sources = parsed.get("sources") if isinstance(parsed, dict) else None
    if not isinstance(sources, list):
        return []
    extracted: list[dict[str, str]] = []
    for item in sources:
        if not isinstance(item, dict):
            continue
        source_id = item.get("source_id")
        content = item.get("content")
        if isinstance(source_id, str) and isinstance(content, str):
            extracted.append({"source_id": source_id, "content": content})
    return extracted


def build_requirement_result(
    sources: list[dict[str, str]],
    *,
    with_conflicts: bool = False,
) -> dict[str, object]:
    """Build a Schema v2 document whose evidence quotes match submitted sources."""
    nonempty = [source for source in sources if source["content"]]
    hard_conditions: list[dict[str, object]] = []
    research_topic = DEFAULT_RESEARCH_TOPIC
    if nonempty:
        first = nonempty[0]
        quote_start, quote_end, quote = _quote_slice(first["content"])
        research_topic = first["content"].strip()[:20] or DEFAULT_RESEARCH_TOPIC
        hard_conditions.append(
            {
                "field": "h_index",
                "operator": "gte",
                "value": 30,
                "description": "H 指数至少 30",
                "evidence": [
                    {
                        "source_id": first["source_id"],
                        "start_offset": quote_start,
                        "end_offset": quote_end,
                        "quote": quote,
                    }
                ],
            }
        )
    conflicts: list[dict[str, object]] = []
    if with_conflicts and len(nonempty) >= MIN_CONFLICT_SOURCES:
        first, second = nonempty[0], nonempty[1]
        first_start, first_end, first_quote = _quote_slice(first["content"])
        second_start, second_end, second_quote = _quote_slice(second["content"])
        conflicts.append(
            {
                "description": "来源对同一条件给出了不同要求",
                "evidence": [
                    {
                        "source_id": first["source_id"],
                        "start_offset": first_start,
                        "end_offset": first_end,
                        "quote": first_quote,
                    },
                    {
                        "source_id": second["source_id"],
                        "start_offset": second_start,
                        "end_offset": second_end,
                        "quote": second_quote,
                    },
                ],
            }
        )
    return {
        "hard_conditions": hard_conditions,
        "preference_conditions": [],
        "research_topic_query": research_topic,
        "unsupported_conditions": [],
        "source_conflicts": conflicts,
    }


def build_search_interpretation_result() -> dict[str, object]:
    """Build a valid search interpretation document that is never dual-empty."""
    return {
        "hard_conditions": [
            {
                "description": "H 指数至少 10",
                "field": "h_index",
                "operator": "gte",
                "value": 10,
            }
        ],
        "research_topic_query": "condensed matter",
        "unsupported_conditions": [],
    }


def _quote_slice(text: str) -> tuple[int, int, str]:
    end = min(len(text), QUOTE_SLICE_CHARS)
    if end == 0:
        return (0, 1, "")
    return (0, end, text[:end])
