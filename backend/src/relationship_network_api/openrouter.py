from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Final, cast, final

import httpx

PROBE_SCHEMA: Final[dict[str, object]] = {
    "additionalProperties": False,
    "properties": {"capability": {"const": "ok", "type": "string"}},
    "required": ["capability"],
    "type": "object",
}
MIN_OUTPUT_TOKENS: Final = 1024
MAX_OUTPUT_TOKENS: Final = 16384
MIN_TIMEOUT_SECONDS: Final = 30
MAX_TIMEOUT_SECONDS: Final = 300
HTTP_BAD_REQUEST: Final = 400
HTTP_UNAUTHORIZED: Final = 401
HTTP_PAYMENT_REQUIRED: Final = 402
HTTP_FORBIDDEN: Final = 403
HTTP_REQUEST_TIMEOUT: Final = 408
HTTP_CONFLICT: Final = 409
HTTP_NOT_FOUND: Final = 404
HTTP_TOO_MANY_REQUESTS: Final = 429
HTTP_SERVER_ERROR: Final = 500


@dataclass(frozen=True)
class CandidateConfiguration:
    model: str
    prompt_version_id: str
    temperature: float = 0
    max_output_tokens: int = 8192
    request_timeout_seconds: int = 180

    def __post_init__(self) -> None:
        """Validate the deliberately small online configuration surface."""
        if not self.model.strip():
            message = "model must not be empty"
            raise ValueError(message)
        if not self.prompt_version_id.strip():
            message = "prompt_version_id must not be empty"
            raise ValueError(message)
        if not 0 <= self.temperature <= 1:
            message = "temperature must be between 0 and 1"
            raise ValueError(message)
        if not MIN_OUTPUT_TOKENS <= self.max_output_tokens <= MAX_OUTPUT_TOKENS:
            message = "max_output_tokens must be between 1024 and 16384"
            raise ValueError(message)
        if not MIN_TIMEOUT_SECONDS <= self.request_timeout_seconds <= MAX_TIMEOUT_SECONDS:
            message = "request_timeout_seconds must be between 30 and 300"
            raise ValueError(message)

    def sanitized_snapshot(self) -> dict[str, object]:
        return {
            "max_output_tokens": self.max_output_tokens,
            "model": self.model,
            "prompt_version_id": self.prompt_version_id,
            "request_timeout_seconds": self.request_timeout_seconds,
            "temperature": self.temperature,
        }


@dataclass(frozen=True)
class OpenRouterClientConfig:
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    site_url: str = ""
    site_name: str = "Relationship Network"


@dataclass(frozen=True)
class OpenRouterProbeResult:
    provider_request_id: str | None
    actual_model: str | None
    actual_provider: str | None
    exchange: OpenRouterResponseExchange


@dataclass(frozen=True)
class OpenRouterResponseExchange:
    """Provider response facts retained without request secrets or log rendering."""

    status_code: int
    headers: dict[str, str]
    raw_body: bytes


@dataclass(frozen=True)
class OpenRouterGenerationMetadata:
    generation_id: str
    actual_model: str | None
    actual_provider: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    cost: float | None
    exchange: OpenRouterResponseExchange


@final
class OpenRouterAdapterError(RuntimeError):
    def __init__(  # noqa: PLR0913
        self,
        category: str,
        *,
        retryable: bool,
        outcome_unknown: bool = False,
        retry_after_seconds: int | None = None,
        status_code: int | None = None,
        exchange: OpenRouterResponseExchange | None = None,
    ) -> None:
        super().__init__(category)
        self.category: str = category
        self.retryable: bool = retryable
        self.outcome_unknown: bool = outcome_unknown
        self.retry_after_seconds: int | None = retry_after_seconds
        self.status_code: int | None = status_code
        self.exchange: OpenRouterResponseExchange | None = exchange


@final
class OpenRouterAdapter:
    def __init__(
        self,
        config: OpenRouterClientConfig,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config: OpenRouterClientConfig = config
        self._client: httpx.AsyncClient | None = client

    async def probe(self, candidate: CandidateConfiguration) -> OpenRouterProbeResult:
        payload = self.build_probe_payload(candidate)
        try:
            response = await self._post(payload, timeout_seconds=candidate.request_timeout_seconds)
        except httpx.TimeoutException as error:
            category = "timeout"
            raise OpenRouterAdapterError(
                category,
                retryable=True,
                outcome_unknown=True,
            ) from error
        except httpx.NetworkError as error:
            category = "network_error"
            raise OpenRouterAdapterError(
                category,
                retryable=True,
                outcome_unknown=True,
            ) from error
        if response.status_code >= HTTP_BAD_REQUEST:
            raise self._classify_http_error(response)
        return self._parse_probe_response(response)

    async def fetch_generation(
        self,
        generation_id: str,
        *,
        timeout_seconds: int = 30,
    ) -> OpenRouterGenerationMetadata:
        """Fetch delayed usage, cost, model, and provider facts by generation ID."""
        headers = {"Authorization": f"Bearer {self._config.api_key}"}
        url = f"{self._config.base_url.rstrip('/')}/generation"
        try:
            if self._client is not None:
                response = await self._client.get(
                    url,
                    headers=headers,
                    params={"id": generation_id},
                    timeout=timeout_seconds,
                )
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        url,
                        headers=headers,
                        params={"id": generation_id},
                        timeout=timeout_seconds,
                    )
        except httpx.TimeoutException as error:
            category = "timeout"
            raise OpenRouterAdapterError(category, retryable=True) from error
        except httpx.NetworkError as error:
            category = "network_error"
            raise OpenRouterAdapterError(category, retryable=True) from error
        if response.status_code >= HTTP_BAD_REQUEST:
            raise self._classify_http_error(response)
        exchange = _response_exchange(response)
        try:
            outer = _object_mapping(json.loads(exchange.raw_body))
            raw_data = outer.get("data", outer)
            data = _object_mapping(raw_data)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            category = "invalid_generation_metadata"
            raise OpenRouterAdapterError(
                category,
                retryable=True,
                exchange=exchange,
            ) from error
        usage = data.get("usage")
        usage_data = cast("dict[str, object]", usage) if isinstance(usage, dict) else {}
        prompt_tokens = _optional_int(usage_data.get("prompt_tokens", data.get("tokens_prompt")))
        completion_tokens = _optional_int(
            usage_data.get("completion_tokens", data.get("tokens_completion"))
        )
        total_tokens = _optional_int(usage_data.get("total_tokens"))
        if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
            total_tokens = prompt_tokens + completion_tokens
        return OpenRouterGenerationMetadata(
            generation_id=generation_id,
            actual_model=_optional_string(data.get("model")),
            actual_provider=_optional_string(data.get("provider_name", data.get("provider"))),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=_optional_float(data.get("total_cost", data.get("cost"))),
            exchange=exchange,
        )

    def build_probe_payload(self, candidate: CandidateConfiguration) -> dict[str, object]:
        return {
            "max_tokens": candidate.max_output_tokens,
            "messages": [
                {
                    "content": (
                        "Return only the JSON object required by the response schema. "
                        "This is a fixed platform capability probe and contains no business data."
                    ),
                    "role": "system",
                },
                {"content": "Report capability as ok.", "role": "user"},
            ],
            "model": candidate.model,
            "provider": {
                "data_collection": "deny",
                "require_parameters": True,
                "zdr": True,
            },
            "response_format": {
                "json_schema": {
                    "name": "relationship_network_config_probe",
                    "schema": PROBE_SCHEMA,
                    "strict": True,
                },
                "type": "json_schema",
            },
            "stream": False,
            "temperature": candidate.temperature,
        }

    async def _post(self, payload: dict[str, object], *, timeout_seconds: int) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        if self._config.site_url:
            headers["HTTP-Referer"] = self._config.site_url
        if self._config.site_name:
            headers["X-OpenRouter-Title"] = self._config.site_name
        url = f"{self._config.base_url.rstrip('/')}/chat/completions"
        if self._client is not None:
            return await self._client.post(
                url, headers=headers, json=payload, timeout=timeout_seconds
            )
        async with httpx.AsyncClient() as client:
            return await client.post(url, headers=headers, json=payload, timeout=timeout_seconds)

    @staticmethod
    def _classify_http_error(response: httpx.Response) -> OpenRouterAdapterError:
        exchange = _response_exchange(response)
        retry_after = _parse_retry_after(response.headers.get("Retry-After"))
        if response.status_code == HTTP_UNAUTHORIZED:
            category = "authentication_failed"
        elif response.status_code == HTTP_PAYMENT_REQUIRED:
            category = "insufficient_balance"
        elif response.status_code == HTTP_FORBIDDEN:
            category = "privacy_routing_rejected"
        elif response.status_code == HTTP_NOT_FOUND:
            category = "model_unavailable"
        elif response.status_code == HTTP_TOO_MANY_REQUESTS:
            return OpenRouterAdapterError(
                "rate_limited",
                retryable=True,
                retry_after_seconds=retry_after,
                status_code=response.status_code,
                exchange=exchange,
            )
        elif response.status_code >= HTTP_SERVER_ERROR or response.status_code in {
            HTTP_REQUEST_TIMEOUT,
            HTTP_CONFLICT,
        }:
            return OpenRouterAdapterError(
                "upstream_unavailable",
                retryable=True,
                retry_after_seconds=retry_after,
                status_code=response.status_code,
                exchange=exchange,
            )
        else:
            category = _classify_bad_request(response)
        return OpenRouterAdapterError(
            category,
            retryable=False,
            status_code=response.status_code,
            exchange=exchange,
        )

    @staticmethod
    def _parse_probe_response(response: httpx.Response) -> OpenRouterProbeResult:
        exchange = _response_exchange(response)
        try:
            body = cast("dict[str, object]", json.loads(exchange.raw_body))
            choices = cast("list[object]", body["choices"])
            choice = cast("dict[str, object]", choices[0])
            message = cast("dict[str, object]", choice["message"])
            raw_content = message["content"]
            content = json.loads(raw_content) if isinstance(raw_content, str) else raw_content
        except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            category = "invalid_structured_output"
            raise OpenRouterAdapterError(
                category,
                retryable=True,
                exchange=exchange,
            ) from error
        if content != {"capability": "ok"}:
            category = "invalid_structured_output"
            raise OpenRouterAdapterError(category, retryable=True, exchange=exchange)
        return OpenRouterProbeResult(
            provider_request_id=_optional_string(body.get("id")),
            actual_model=_optional_string(body.get("model")),
            actual_provider=_optional_string(body.get("provider")),
            exchange=exchange,
        )


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _object_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        message = "expected a JSON object"
        raise TypeError(message)
    return cast("dict[str, object]", value)


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _optional_float(value: object) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    parsed = float(value)
    return parsed if parsed >= 0 else None


def _response_exchange(response: httpx.Response) -> OpenRouterResponseExchange:
    return OpenRouterResponseExchange(
        status_code=response.status_code,
        headers=dict(response.headers),
        raw_body=response.content,
    )


def _classify_bad_request(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None
    message = json.dumps(payload, ensure_ascii=False).lower()
    if "balance" in message or "credit" in message:
        return "insufficient_balance"
    if "zdr" in message or "data collection" in message or "privacy" in message:
        return "privacy_routing_rejected"
    if "model" in message:
        return "model_unavailable"
    if "parameter" in message or "response_format" in message or "json_schema" in message:
        return "unsupported_parameters"
    return "invalid_request"


def _parse_retry_after(raw: str | None) -> int | None:
    if raw is None:
        return None
    try:
        seconds = int(raw)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(raw)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        seconds = int((retry_at - datetime.now(UTC)).total_seconds())
    return max(seconds, 0)
