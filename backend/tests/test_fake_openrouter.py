import json
from typing import cast

import httpx
import pytest

from relationship_network_api.fake_openrouter import (
    FAKE_PROVIDER,
    FAKE_REQUEST_ID,
    MODEL_DELAYED_GENERATION,
    MODEL_DISCONNECT,
    MODEL_INVALID_STRUCTURE,
    MODEL_PROVIDER_DENIED,
    MODEL_RATE_LIMITED,
    MODEL_SEARCH_INTERPRETATION_INVALID,
    MODEL_SERVER_ERROR,
    MODEL_TIMEOUT,
    MODEL_WITH_CONFLICTS,
    REQUIRED_ROUTING,
    REQUIREMENT_SCHEMA_NAME,
    SEARCH_INTERPRETATION_SCHEMA_NAME,
    app,
    build_requirement_result,
    build_search_interpretation_result,
    reset_fake_openrouter,
    timing,
)
from relationship_network_api.job_requirement_validation import validate_requirement_result
from relationship_network_api.llm_assets import manifest


def _probe_payload(model: str) -> dict[str, object]:
    return {
        "max_tokens": 1024,
        "messages": [{"content": "Report capability as ok.", "role": "user"}],
        "model": model,
        "provider": REQUIRED_ROUTING,
        "response_format": {
            "json_schema": {
                "name": REQUIREMENT_SCHEMA_NAME,
                "schema": {"type": "object"},
                "strict": True,
            },
            "type": "json_schema",
        },
        "stream": False,
        "temperature": 0,
    }


def _search_payload(model: str) -> dict[str, object]:
    return {
        "max_tokens": 1024,
        "messages": [
            {"content": "system", "role": "system"},
            {"content": '{"search_utterance":"h-index above 10 condensed matter"}', "role": "user"},
        ],
        "model": model,
        "provider": REQUIRED_ROUTING,
        "response_format": {
            "json_schema": {
                "name": SEARCH_INTERPRETATION_SCHEMA_NAME,
                "schema": {"type": "object"},
                "strict": True,
            },
            "type": "json_schema",
        },
        "stream": False,
        "temperature": 0,
    }


def _requirement_payload(model: str, sources: list[dict[str, str]]) -> dict[str, object]:
    return {
        "max_tokens": 1024,
        "messages": [
            {"content": "system", "role": "system"},
            {
                "content": json.dumps(
                    {"sources": sources}, ensure_ascii=False, separators=(",", ":")
                ),
                "role": "user",
            },
        ],
        "model": model,
        "provider": REQUIRED_ROUTING,
        "response_format": {
            "json_schema": {
                "name": REQUIREMENT_SCHEMA_NAME,
                "schema": {"type": "object"},
                "strict": True,
            },
            "type": "json_schema",
        },
        "stream": False,
        "temperature": 0,
    }


@pytest.fixture(autouse=True)
def _reset_fake() -> None:
    reset_fake_openrouter()


@pytest.mark.anyio
async def test_requirement_and_search_interpretation_branch_on_schema_name() -> None:
    sources = [{"source_id": "job-description", "content": "需要海外华人研究人工智能"}]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        unknown = await client.post(
            "/api/v1/chat/completions",
            json={
                **_requirement_payload("x-ai/grok-4.5", sources),
                "response_format": {
                    "json_schema": {
                        "name": "relationship_network_config_probe",
                        "schema": {"type": "object"},
                        "strict": True,
                    },
                    "type": "json_schema",
                },
            },
        )
        requirement = await client.post(
            "/api/v1/chat/completions",
            json=_requirement_payload("x-ai/grok-4.5", sources),
        )
        search = await client.post(
            "/api/v1/chat/completions",
            json=_search_payload("x-ai/grok-4.5"),
        )
        invalid_search = await client.post(
            "/api/v1/chat/completions",
            json=_search_payload(MODEL_SEARCH_INTERPRETATION_INVALID),
        )
        valid_parsing_invalid_search = await client.post(
            "/api/v1/chat/completions",
            json=_requirement_payload(MODEL_SEARCH_INTERPRETATION_INVALID, sources),
        )

    assert json.loads(unknown.json()["choices"][0]["message"]["content"]) == {
        "capability": "not-ok"
    }

    requirement_body = requirement.json()
    content = json.loads(requirement_body["choices"][0]["message"]["content"])
    schema = manifest.read_requirement_schema(manifest.JOB_REQUIREMENT_SCHEMA_V2.id)
    validated = validate_requirement_result(
        content,
        schema=schema,
        asset=manifest.JOB_REQUIREMENT_SCHEMA_V2,
        source_texts={"job-description": "需要海外华人研究人工智能"},
    )
    assert validated["research_topic_query"]
    assert validated["hard_conditions"]

    search_content = json.loads(search.json()["choices"][0]["message"]["content"])
    assert search_content == build_search_interpretation_result()
    assert json.loads(invalid_search.json()["choices"][0]["message"]["content"]) == {
        "capability": "not-ok"
    }
    parsing_ok = json.loads(valid_parsing_invalid_search.json()["choices"][0]["message"]["content"])
    assert parsing_ok["hard_conditions"]


@pytest.mark.anyio
async def test_model_overrides_cover_failure_and_provider_scenarios() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        limited = await client.post(
            "/api/v1/chat/completions", json=_probe_payload(MODEL_RATE_LIMITED)
        )
        invalid = await client.post(
            "/api/v1/chat/completions", json=_probe_payload(MODEL_INVALID_STRUCTURE)
        )
        server_error = await client.post(
            "/api/v1/chat/completions", json=_probe_payload(MODEL_SERVER_ERROR)
        )
        denied = await client.post(
            "/api/v1/chat/completions", json=_probe_payload(MODEL_PROVIDER_DENIED)
        )
        missing_routing = await client.post(
            "/api/v1/chat/completions",
            json={**_probe_payload("test/success"), "provider": {"zdr": False}},
        )

    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "1"
    assert json.loads(invalid.json()["choices"][0]["message"]["content"]) == {
        "capability": "not-ok"
    }
    assert server_error.status_code == 500
    assert denied.status_code == 403
    assert missing_routing.status_code == 400


@pytest.mark.anyio
async def test_timeout_disconnect_and_delayed_generation_are_controllable() -> None:
    timing.hang_seconds = 0.01
    timing.generation_delay_seconds = 60
    sources = [{"source_id": "job-description", "content": "H指数30"}]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        timeout=1,
    ) as client:
        hung = await client.post("/api/v1/chat/completions", json=_probe_payload(MODEL_TIMEOUT))
        with pytest.raises(ConnectionResetError, match="fake openrouter disconnect"):
            _ = await client.post("/api/v1/chat/completions", json=_probe_payload(MODEL_DISCONNECT))
        delayed = await client.post(
            "/api/v1/chat/completions",
            json=_requirement_payload(MODEL_DELAYED_GENERATION, sources),
        )
        pending = await client.get("/api/v1/generation", params={"id": FAKE_REQUEST_ID})
        ready = await client.get("/api/v1/generation", params={"id": "other-id"})

    assert hung.status_code == 200
    assert delayed.status_code == 200
    assert pending.status_code == 404
    assert ready.status_code == 200
    assert ready.json()["data"]["provider_name"] == FAKE_PROVIDER


@pytest.mark.anyio
async def test_conflict_variant_requires_two_sources_and_passes_schema() -> None:
    sources = [
        {"source_id": "job-description", "content": "需要三年经验"},
        {"source_id": "job-material:1", "content": "需要五年经验"},
    ]
    result = build_requirement_result(sources, with_conflicts=True)
    schema = manifest.read_requirement_schema(manifest.JOB_REQUIREMENT_SCHEMA_V2.id)
    validated = validate_requirement_result(
        result,
        schema=schema,
        asset=manifest.JOB_REQUIREMENT_SCHEMA_V2,
        source_texts={item["source_id"]: item["content"] for item in sources},
    )
    conflicts = validated["source_conflicts"]
    assert isinstance(conflicts, list)
    assert len(cast("list[object]", conflicts)) == 1

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/chat/completions",
            json=_requirement_payload(MODEL_WITH_CONFLICTS, sources),
        )
    content = json.loads(response.json()["choices"][0]["message"]["content"])
    assert content["source_conflicts"]
