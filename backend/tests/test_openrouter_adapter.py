import json

import httpx
import pytest

from relationship_network_api.openrouter import (
    CandidateConfiguration,
    OpenRouterAdapter,
    OpenRouterAdapterError,
    OpenRouterClientConfig,
)


def candidate() -> CandidateConfiguration:
    return CandidateConfiguration(
        model="x-ai/grok-4.5",
        prompt_version_id="job-requirement-prompt-v1",
        temperature=0,
        max_output_tokens=8192,
        request_timeout_seconds=180,
    )


@pytest.mark.anyio
async def test_probe_forces_strict_non_streaming_private_same_model_request() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "gen-1",
                "model": "x-ai/grok-4.5",
                "provider": "example-provider",
                "choices": [{"message": {"content": '{"capability":"ok"}'}}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenRouterAdapter(
            OpenRouterClientConfig(
                api_key="secret",
                base_url="https://openrouter.test/api/v1",
                site_url="https://relationship.test",
                site_name="Relationship Network",
            ),
            client=client,
        )
        result = await adapter.probe(candidate())

    body = captured["body"]
    assert isinstance(body, dict)
    assert body["model"] == "x-ai/grok-4.5"
    assert "models" not in body
    assert body["stream"] is False
    assert body["provider"] == {
        "data_collection": "deny",
        "require_parameters": True,
        "zdr": True,
    }
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "relationship_network_config_probe",
            "strict": True,
            "schema": {
                "additionalProperties": False,
                "properties": {"capability": {"const": "ok", "type": "string"}},
                "required": ["capability"],
                "type": "object",
            },
        },
    }
    assert result.provider_request_id == "gen-1"
    assert result.actual_provider == "example-provider"
    assert result.exchange.status_code == 200
    assert b'"gen-1"' in result.exchange.raw_body


@pytest.mark.anyio
async def test_probe_rejects_extra_structured_output_properties() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "gen-invalid",
                "choices": [{"message": {"content": '{"capability":"ok","extra":true}'}}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenRouterAdapter(
            OpenRouterClientConfig(api_key="secret", base_url="https://openrouter.test/api/v1"),
            client=client,
        )
        with pytest.raises(OpenRouterAdapterError) as captured:
            _ = await adapter.probe(candidate())

    assert captured.value.category == "invalid_structured_output"
    assert captured.value.retryable is True
    assert captured.value.outcome_unknown is False
    assert captured.value.exchange is not None
    assert b"gen-invalid" in captured.value.exchange.raw_body


@pytest.mark.anyio
async def test_probe_classifies_throttling_and_retry_after() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "12"}, json={"error": "limited"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenRouterAdapter(
            OpenRouterClientConfig(api_key="secret", base_url="https://openrouter.test/api/v1"),
            client=client,
        )
        with pytest.raises(OpenRouterAdapterError) as captured:
            _ = await adapter.probe(candidate())

    assert captured.value.category == "rate_limited"
    assert captured.value.retryable is True
    assert captured.value.retry_after_seconds == 12
    assert captured.value.exchange is not None
    assert captured.value.exchange.status_code == 429


@pytest.mark.anyio
async def test_probe_classifies_authentication_as_permanent() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "invalid API key"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenRouterAdapter(
            OpenRouterClientConfig(api_key="secret", base_url="https://openrouter.test/api/v1"),
            client=client,
        )
        with pytest.raises(OpenRouterAdapterError) as captured:
            _ = await adapter.probe(candidate())

    assert captured.value.category == "authentication_failed"
    assert captured.value.retryable is False
    assert captured.value.outcome_unknown is False


@pytest.mark.anyio
async def test_probe_marks_transport_timeout_outcome_unknown() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        message = "timed out"
        raise httpx.ReadTimeout(message)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenRouterAdapter(
            OpenRouterClientConfig(api_key="secret", base_url="https://openrouter.test/api/v1"),
            client=client,
        )
        with pytest.raises(OpenRouterAdapterError) as captured:
            _ = await adapter.probe(candidate())

    assert captured.value.category == "timeout"
    assert captured.value.retryable is True
    assert captured.value.outcome_unknown is True
    assert captured.value.exchange is None


@pytest.mark.anyio
async def test_fetch_generation_parses_delayed_usage_cost_and_provider() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["id"] == "gen-1"
        return httpx.Response(
            200,
            json={
                "data": {
                    "id": "gen-1",
                    "model": "x-ai/grok-4.5",
                    "provider_name": "provider-a",
                    "tokens_prompt": 12,
                    "tokens_completion": 7,
                    "cost": 0.0012,
                }
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenRouterAdapter(
            OpenRouterClientConfig(api_key="secret", base_url="https://openrouter.test/api/v1"),
            client=client,
        )
        result = await adapter.fetch_generation("gen-1")

    assert result.actual_provider == "provider-a"
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 7
    assert result.total_tokens == 19
    assert result.cost == 0.0012
