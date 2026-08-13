from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Final, Literal, NoReturn, cast, final
from urllib.parse import quote

import httpx
from pydantic import ValidationError

from relationship_network_api.search_base_contract import (
    AUTHORIZATION_HEADER,
    BEARER_SCHEME,
    CONTRACT_VERSION_HEADER,
    HEALTH_PATH,
    MAX_PERSON_BATCH_SIZE,
    PERSON_BATCH_PATH,
    PERSON_DETAIL_PATH_TEMPLATE,
    PERSON_DETAIL_RESPONSE_ADAPTER,
    PERSON_EVIDENCE_PATH_TEMPLATE,
    PERSON_EVIDENCE_RESPONSE_ADAPTER,
    REQUEST_ID_HEADER,
    SEARCH_CONTRACT_VERSION_V1,
    PersonBatchRequest,
    PersonBatchResponse,
    PersonDetailFound,
    PersonDetailResult,
    PersonEvidenceFound,
    PersonEvidenceResult,
    SearchBaseErrorBody,
    SearchBaseHealthResponse,
)

if TYPE_CHECKING:
    from relationship_network_api.config import AppSettings

type Sleeper = Callable[[float], Awaitable[None]]
type HttpMethod = Literal["GET", "POST"]

logger = logging.getLogger(__name__)

MAX_ATTEMPTS: Final = 3
BACKOFF_BASE_SECONDS: Final = 0.2
HTTP_BAD_REQUEST: Final = 400
HTTP_UNAUTHORIZED: Final = 401
HTTP_FORBIDDEN: Final = 403
HTTP_CONFLICT: Final = 409
HTTP_TOO_MANY_REQUESTS: Final = 429
HTTP_SERVER_ERROR: Final = 500
RETRYABLE_CATEGORIES: Final[frozenset[str]] = frozenset(
    {"timeout", "network_error", "rate_limited", "unavailable"}
)
FORBIDDEN_CONTACT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "email",
        "e-mail",
        "emails",
        "phone",
        "phones",
        "telephone",
        "telephones",
        "mobile",
        "mobiles",
        "tel",
        "tels",
    }
)


@dataclass(frozen=True)
class SearchBaseClientConfig:
    api_key: str
    base_url: str
    timeout_seconds: float = 10
    contract_version: str = SEARCH_CONTRACT_VERSION_V1

    def __post_init__(self) -> None:
        """Reject empty routing values while allowing empty keys for auth tests."""
        if not self.base_url.strip():
            message = "base_url must not be empty"
            raise ValueError(message)
        if self.timeout_seconds <= 0:
            message = "timeout_seconds must be positive"
            raise ValueError(message)
        if not self.contract_version.strip():
            message = "contract_version must not be empty"
            raise ValueError(message)


@final
class SearchBaseAdapterError(RuntimeError):
    def __init__(
        self,
        category: str,
        *,
        retryable: bool,
        retry_after_seconds: int | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(category)
        self.category: str = category
        self.retryable: bool = retryable
        self.retry_after_seconds: int | None = retry_after_seconds
        self.status_code: int | None = status_code


@final
class SearchBaseAdapter:
    def __init__(
        self,
        config: SearchBaseClientConfig,
        *,
        client: httpx.AsyncClient | None = None,
        sleeper: Sleeper = asyncio.sleep,
    ) -> None:
        self._config: SearchBaseClientConfig = config
        self._client: httpx.AsyncClient | None = client
        self._sleeper: Sleeper = sleeper

    async def check_health(self, *, request_id: str | None = None) -> SearchBaseHealthResponse:
        resolved_request_id = request_id or str(uuid.uuid4())
        response = await self._request("GET", HEALTH_PATH, resolved_request_id)
        result = _parse_health_response(response, resolved_request_id)
        logger.info(
            "search-base health ok request_id=%s data_version=%s",
            result.request_id,
            result.data_version,
        )
        return result

    async def get_person(
        self,
        canonical_person_id: str,
        *,
        request_id: str | None = None,
    ) -> PersonDetailResult:
        _reject_blank_person_id(canonical_person_id)
        resolved_request_id = request_id or str(uuid.uuid4())
        path = PERSON_DETAIL_PATH_TEMPLATE.format(
            canonical_person_id=quote(canonical_person_id, safe="")
        )
        response = await self._request("GET", path, resolved_request_id)
        result = _parse_person_detail_response(response, resolved_request_id, canonical_person_id)
        logger.info(
            "search-base person %s request_id=%s data_version=%s outcome=%s",
            canonical_person_id,
            result.request_id,
            result.data_version,
            result.outcome,
        )
        return result

    async def get_persons(
        self,
        canonical_person_ids: Sequence[str],
        *,
        request_id: str | None = None,
    ) -> PersonBatchResponse:
        ids = list(canonical_person_ids)
        if len(ids) > MAX_PERSON_BATCH_SIZE:
            _raise_invalid_query()
        for person_id in ids:
            _reject_blank_person_id(person_id)
        resolved_request_id = request_id or str(uuid.uuid4())
        body = PersonBatchRequest(canonical_person_ids=ids)
        response = await self._request(
            "POST",
            PERSON_BATCH_PATH,
            resolved_request_id,
            json_body=body.model_dump(mode="json"),
        )
        result = _parse_person_batch_response(response, resolved_request_id)
        logger.info(
            "search-base person batch ok request_id=%s data_version=%s found=%s absent=%s",
            result.request_id,
            result.data_version,
            len(result.persons),
            len(result.currently_absent_ids),
        )
        return result

    async def get_person_evidence(
        self,
        canonical_person_id: str,
        *,
        request_id: str | None = None,
    ) -> PersonEvidenceResult:
        _reject_blank_person_id(canonical_person_id)
        resolved_request_id = request_id or str(uuid.uuid4())
        path = PERSON_EVIDENCE_PATH_TEMPLATE.format(
            canonical_person_id=quote(canonical_person_id, safe="")
        )
        response = await self._request("GET", path, resolved_request_id)
        result = _parse_person_evidence_response(response, resolved_request_id, canonical_person_id)
        logger.info(
            "search-base person evidence %s request_id=%s data_version=%s outcome=%s",
            canonical_person_id,
            result.request_id,
            result.data_version,
            result.outcome,
        )
        return result

    async def _request(
        self,
        method: HttpMethod,
        path: str,
        request_id: str,
        *,
        json_body: dict[str, object] | None = None,
    ) -> httpx.Response:
        if self._client is not None:
            return await self._request_with_retries(
                self._client,
                method,
                path,
                request_id,
                json_body=json_body,
            )
        timeout = httpx.Timeout(self._config.timeout_seconds)
        async with httpx.AsyncClient(
            timeout=timeout,
            transport=httpx.AsyncHTTPTransport(retries=0),
        ) as client:
            return await self._request_with_retries(
                client,
                method,
                path,
                request_id,
                json_body=json_body,
            )

    async def _request_with_retries(
        self,
        client: httpx.AsyncClient,
        method: HttpMethod,
        path: str,
        request_id: str,
        *,
        json_body: dict[str, object] | None,
    ) -> httpx.Response:
        last_error: SearchBaseAdapterError | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return await self._send(
                    client,
                    method,
                    path,
                    request_id,
                    json_body=json_body,
                )
            except SearchBaseAdapterError as error:
                last_error = error
                if not error.retryable or attempt >= MAX_ATTEMPTS:
                    logger.warning(
                        "search-base request failed category=%s retryable=%s request_id=%s",
                        error.category,
                        error.retryable,
                        request_id,
                    )
                    raise
                await self._sleeper(_backoff_seconds(attempt, error.retry_after_seconds))
        if last_error is None:
            message = "search-base request ended without a result"
            raise RuntimeError(message)
        raise last_error

    async def _send(
        self,
        client: httpx.AsyncClient,
        method: HttpMethod,
        path: str,
        request_id: str,
        *,
        json_body: dict[str, object] | None,
    ) -> httpx.Response:
        headers = {
            AUTHORIZATION_HEADER: f"{BEARER_SCHEME} {self._config.api_key}",
            CONTRACT_VERSION_HEADER: self._config.contract_version,
            REQUEST_ID_HEADER: request_id,
        }
        url = f"{self._config.base_url.rstrip('/')}{path}"
        timeout = httpx.Timeout(self._config.timeout_seconds)
        try:
            response = await client.request(
                method,
                url,
                headers=headers,
                json=json_body,
                timeout=timeout,
            )
        except httpx.TimeoutException as error:
            category = "timeout"
            raise SearchBaseAdapterError(category, retryable=True) from error
        except httpx.NetworkError as error:
            category = "network_error"
            raise SearchBaseAdapterError(category, retryable=True) from error
        if response.status_code >= HTTP_BAD_REQUEST:
            raise self._classify_http_error(response)
        return response

    @staticmethod
    def _classify_http_error(response: httpx.Response) -> SearchBaseAdapterError:
        retry_after = _parse_retry_after(response.headers.get("Retry-After"))
        category = _category_for_status(response.status_code)
        if category is None:
            body = _try_error_body(response)
            category = body.category if body is not None else "invalid_response"
        retryable = category in RETRYABLE_CATEGORIES
        return SearchBaseAdapterError(
            category,
            retryable=retryable,
            retry_after_seconds=retry_after if retryable else None,
            status_code=response.status_code,
        )


def search_base_adapter_from_settings(
    settings: AppSettings,
    *,
    client: httpx.AsyncClient | None = None,
    sleeper: Sleeper = asyncio.sleep,
) -> SearchBaseAdapter:
    api_key = (
        ""
        if settings.search_base_api_key is None
        else settings.search_base_api_key.get_secret_value()
    )
    return SearchBaseAdapter(
        SearchBaseClientConfig(
            api_key=api_key,
            base_url=settings.search_base_base_url,
            timeout_seconds=settings.search_base_timeout_seconds,
            contract_version=settings.search_base_contract_version,
        ),
        client=client,
        sleeper=sleeper,
    )


def _reject_blank_person_id(canonical_person_id: str) -> None:
    if not canonical_person_id.strip():
        _raise_invalid_query()


def _raise_invalid_query() -> NoReturn:
    category = "invalid_query"
    raise SearchBaseAdapterError(category, retryable=False)


def _parse_health_response(
    response: httpx.Response,
    request_id: str,
) -> SearchBaseHealthResponse:
    try:
        parsed = SearchBaseHealthResponse.model_validate(response.json())
    except (TypeError, ValueError, ValidationError) as error:
        raise _invalid_response(response.status_code) from error
    _ensure_echoed_request_id(parsed.request_id, request_id, response.status_code)
    return parsed


def _parse_person_detail_response(
    response: httpx.Response,
    request_id: str,
    canonical_person_id: str,
) -> PersonDetailResult:
    payload = _load_json_payload(response)
    _reject_contact_keys(payload, response.status_code)
    try:
        parsed = PERSON_DETAIL_RESPONSE_ADAPTER.validate_python(payload)
    except ValidationError as error:
        raise _invalid_response(response.status_code) from error
    _ensure_echoed_request_id(parsed.request_id, request_id, response.status_code)
    echoed_id = (
        parsed.person.canonical_person_id
        if isinstance(parsed, PersonDetailFound)
        else parsed.canonical_person_id
    )
    if echoed_id != canonical_person_id:
        raise _invalid_response(response.status_code)
    return parsed


def _parse_person_batch_response(
    response: httpx.Response,
    request_id: str,
) -> PersonBatchResponse:
    payload = _load_json_payload(response)
    _reject_contact_keys(payload, response.status_code)
    try:
        parsed = PersonBatchResponse.model_validate(payload)
    except ValidationError as error:
        raise _invalid_response(response.status_code) from error
    _ensure_echoed_request_id(parsed.request_id, request_id, response.status_code)
    return parsed


def _parse_person_evidence_response(
    response: httpx.Response,
    request_id: str,
    canonical_person_id: str,
) -> PersonEvidenceResult:
    payload = _load_json_payload(response)
    _reject_contact_keys(payload, response.status_code)
    try:
        parsed = PERSON_EVIDENCE_RESPONSE_ADAPTER.validate_python(payload)
    except ValidationError as error:
        raise _invalid_response(response.status_code) from error
    _ensure_echoed_request_id(parsed.request_id, request_id, response.status_code)
    if parsed.canonical_person_id != canonical_person_id:
        raise _invalid_response(response.status_code)
    if isinstance(parsed, PersonEvidenceFound):
        _ensure_publication_provenance_ids(parsed, response.status_code)
    return parsed


def _ensure_publication_provenance_ids(
    evidence: PersonEvidenceFound,
    status_code: int,
) -> None:
    publication_ids = {item.publication_id for item in evidence.publications}
    for claim in evidence.field_provenance:
        if claim.source_kind == "publication" and claim.source_id not in publication_ids:
            raise _invalid_response(status_code)


def _load_json_payload(response: httpx.Response) -> object:
    try:
        return response.json()
    except (TypeError, ValueError) as error:
        raise _invalid_response(response.status_code) from error


def _ensure_echoed_request_id(echoed: str, request_id: str, status_code: int) -> None:
    if echoed != request_id:
        raise _invalid_response(status_code)


def _reject_contact_keys(payload: object, status_code: int) -> None:
    if _payload_contains_contact_keys(payload):
        raise _invalid_response(status_code)


def _payload_contains_contact_keys(payload: object) -> bool:
    if isinstance(payload, dict):
        mapping = cast("dict[object, object]", payload)
        for key, value in mapping.items():
            if str(key).lower() in FORBIDDEN_CONTACT_KEYS:
                return True
            if _payload_contains_contact_keys(value):
                return True
        return False
    if isinstance(payload, list):
        items = cast("list[object]", payload)
        return any(_payload_contains_contact_keys(item) for item in items)
    return False


def _invalid_response(status_code: int) -> SearchBaseAdapterError:
    category = "invalid_response"
    return SearchBaseAdapterError(category, retryable=False, status_code=status_code)


def _category_for_status(status_code: int) -> str | None:
    if status_code == HTTP_UNAUTHORIZED:
        return "unauthenticated"
    if status_code == HTTP_FORBIDDEN:
        return "forbidden"
    if status_code == HTTP_CONFLICT:
        return "contract_version_incompatible"
    if status_code == HTTP_TOO_MANY_REQUESTS:
        return "rate_limited"
    if status_code >= HTTP_SERVER_ERROR:
        return "unavailable"
    return None


def _try_error_body(response: httpx.Response) -> SearchBaseErrorBody | None:
    try:
        return SearchBaseErrorBody.model_validate(response.json())
    except (TypeError, ValueError, ValidationError):
        return None


def _backoff_seconds(failed_attempt: int, retry_after_seconds: int | None) -> float:
    if retry_after_seconds is not None:
        return float(retry_after_seconds)
    return BACKOFF_BASE_SECONDS * (2 ** (failed_attempt - 1))


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
