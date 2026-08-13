"""Deterministic fake search base used by Compose, CI, and adapter contract tests."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, fields
from typing import Final

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from relationship_network_api.search_base_contract import (
    AUTHORIZATION_HEADER,
    BEARER_SCHEME,
    CONTRACT_VERSION_HEADER,
    EXECUTABLE_SCHEMA_VERSIONS,
    MAX_PERSON_BATCH_SIZE,
    REQUEST_ID_HEADER,
    SEARCH_CONTRACT_VERSION_V1,
    CanonicalPersonFields,
    PersonBatchRequest,
    PersonBatchResponse,
    PersonCurrentAbsence,
    PersonDetailFound,
    SearchBaseErrorBody,
    SearchBaseErrorCategory,
    SearchBaseHealthResponse,
)

DEFAULT_SERVICE_API_KEY: Final = "fake-search-base-key"
DEFAULT_DATA_VERSION: Final = "dv-seed-001"
SEEDED_PERSON_ID: Final = "cp-seed-001"
SEEDED_PERSON_WITHOUT_RANKS_ID: Final = "cp-seed-002"
SEEDED_ABSENT_PERSON_ID: Final = "cp-absent-001"
HTTP_BAD_REQUEST: Final = 400
HTTP_UNAUTHORIZED: Final = 401
HTTP_FORBIDDEN: Final = 403
HTTP_CONFLICT: Final = 409
HTTP_TOO_MANY_REQUESTS: Final = 429
HTTP_SERVER_ERROR: Final = 500

SEEDED_PERSONS: Final[dict[str, CanonicalPersonFields]] = {
    SEEDED_PERSON_ID: CanonicalPersonFields(
        canonical_person_id=SEEDED_PERSON_ID,
        historical_source_ids=("src-openalex-001", "src-orcid-001"),
        display_name="Wei Zhang",
        current_affiliation="Tsinghua University",
        country="CN",
        chinese_identity="国内华人",
        h_index=42,
        total_citations=3180,
        qs_top200_rank=25,
        world_top500_rank=18,
        has_contact=True,
    ),
    SEEDED_PERSON_WITHOUT_RANKS_ID: CanonicalPersonFields(
        canonical_person_id=SEEDED_PERSON_WITHOUT_RANKS_ID,
        historical_source_ids=(),
        display_name="Elena Rossi",
        current_affiliation="University of Bologna",
        country="IT",
        chinese_identity="外国人",
        h_index=18,
        total_citations=640,
        qs_top200_rank=None,
        world_top500_rank=None,
        has_contact=False,
    ),
}

app = FastAPI(title="Fake Search Base")


@dataclass
class FakeSearchBaseState:
    """In-memory scenario switches reset between tests."""

    service_api_key: str = DEFAULT_SERVICE_API_KEY
    current_data_version: str = DEFAULT_DATA_VERSION
    deny_auth: bool = False
    forbidden: bool = False
    incompatible_contract: bool = False
    hang_seconds: float = 0.0
    status_5xx: bool = False
    rate_limited: bool = False
    retry_after_seconds: int | None = None
    request_count: int = 0
    last_authorization: str = ""
    last_contract_version: str = ""
    last_request_id: str = ""


state = FakeSearchBaseState()


def reset_fake_search_base() -> None:
    """Restore scenario switches and captured headers between tests."""
    defaults = FakeSearchBaseState()
    for field in fields(FakeSearchBaseState):
        setattr(state, field.name, getattr(defaults, field.name))


@app.get("/health")
async def liveness() -> JSONResponse:
    return JSONResponse(content={"status": "ok"})


@app.get("/v1/health")
async def health(request: Request) -> Response:
    guarded = await _guard(request)
    if guarded is not None:
        return guarded
    payload = SearchBaseHealthResponse(
        request_id=_echo_request_id(),
        contract_version=SEARCH_CONTRACT_VERSION_V1,
        executable_schema_versions=EXECUTABLE_SCHEMA_VERSIONS,
        data_version=state.current_data_version,
        status="ok",
    )
    return _json_payload(payload)


@app.get("/v1/persons/{canonical_person_id}")
async def person_detail(canonical_person_id: str, request: Request) -> Response:
    guarded = await _guard(request)
    if guarded is not None:
        return guarded
    person = SEEDED_PERSONS.get(canonical_person_id)
    request_id = _echo_request_id()
    if person is None:
        payload: PersonDetailFound | PersonCurrentAbsence = PersonCurrentAbsence(
            outcome="current_absence",
            request_id=request_id,
            data_version=state.current_data_version,
            canonical_person_id=canonical_person_id,
        )
    else:
        payload = PersonDetailFound(
            outcome="found",
            request_id=request_id,
            data_version=state.current_data_version,
            person=person,
        )
    return _json_payload(payload)


@app.post("/v1/persons/batch")
async def person_batch(request: Request) -> Response:
    guarded = await _guard(request)
    if guarded is not None:
        return guarded
    try:
        body = PersonBatchRequest.model_validate(await request.json())
    except (TypeError, ValueError, ValidationError):
        return _error_response("invalid_query", status_code=HTTP_BAD_REQUEST, retryable=False)
    if len(body.canonical_person_ids) > MAX_PERSON_BATCH_SIZE:
        return _error_response("invalid_query", status_code=HTTP_BAD_REQUEST, retryable=False)
    found: list[CanonicalPersonFields] = []
    absent: list[str] = []
    for person_id in body.canonical_person_ids:
        person = SEEDED_PERSONS.get(person_id)
        if person is None:
            absent.append(person_id)
        else:
            found.append(person)
    payload = PersonBatchResponse(
        request_id=_echo_request_id(),
        data_version=state.current_data_version,
        persons=tuple(found),
        currently_absent_ids=tuple(absent),
    )
    return _json_payload(payload)


async def _guard(request: Request) -> Response | None:
    state.request_count += 1
    state.last_authorization = request.headers.get(AUTHORIZATION_HEADER, "")
    state.last_contract_version = request.headers.get(CONTRACT_VERSION_HEADER, "")
    state.last_request_id = request.headers.get(REQUEST_ID_HEADER, "")
    if state.hang_seconds > 0:
        await asyncio.sleep(state.hang_seconds)
    auth_error = _authentication_error(request)
    if auth_error is not None:
        return auth_error
    if state.forbidden:
        return _error_response("forbidden", status_code=HTTP_FORBIDDEN, retryable=False)
    contract_version = request.headers.get(CONTRACT_VERSION_HEADER, "")
    if state.incompatible_contract or contract_version != SEARCH_CONTRACT_VERSION_V1:
        return _error_response(
            "contract_version_incompatible",
            status_code=HTTP_CONFLICT,
            retryable=False,
        )
    if state.rate_limited:
        return _error_response(
            "rate_limited",
            status_code=HTTP_TOO_MANY_REQUESTS,
            retryable=True,
            retry_after_seconds=state.retry_after_seconds,
        )
    if state.status_5xx:
        return _error_response("unavailable", status_code=HTTP_SERVER_ERROR, retryable=True)
    return None


def _echo_request_id() -> str:
    return state.last_request_id or "missing-request-id"


def _json_payload(
    payload: SearchBaseHealthResponse
    | PersonDetailFound
    | PersonCurrentAbsence
    | PersonBatchResponse,
) -> JSONResponse:
    return JSONResponse(
        content=payload.model_dump(mode="json"),
        headers={REQUEST_ID_HEADER: payload.request_id},
    )


def _authentication_error(request: Request) -> JSONResponse | None:
    if state.deny_auth:
        return _error_response("unauthenticated", status_code=HTTP_UNAUTHORIZED, retryable=False)
    token = _bearer_token(request)
    if token is None or token != state.service_api_key:
        return _error_response("unauthenticated", status_code=HTTP_UNAUTHORIZED, retryable=False)
    return None


def _bearer_token(request: Request) -> str | None:
    raw = request.headers.get(AUTHORIZATION_HEADER)
    if raw is None:
        return None
    scheme, separator, token = raw.partition(" ")
    if separator == "" or scheme.lower() != BEARER_SCHEME.lower() or not token.strip():
        return None
    return token.strip()


def _error_response(
    category: SearchBaseErrorCategory,
    *,
    status_code: int,
    retryable: bool,
    retry_after_seconds: int | None = None,
) -> JSONResponse:
    body = SearchBaseErrorBody(category=category, retryable=retryable)
    headers: dict[str, str] = {}
    if retry_after_seconds is not None:
        headers["Retry-After"] = str(retry_after_seconds)
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers=headers,
    )
