from typing import TYPE_CHECKING, cast, final

import pytest

from relationship_network_api import llm_configuration_service as service
from relationship_network_api.llm_assets import manifest
from relationship_network_api.llm_assets.manifest import (
    CALL_TYPE_JOB_REQUIREMENT_PARSING,
    CALL_TYPE_SEARCH_INTERPRETATION,
)
from relationship_network_api.openrouter import CallTypeBinding, CandidateConfiguration

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@final
class FakeResult:
    def __init__(self, value: object | None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object | None:
        return self.value


@final
class FakeSession:
    def __init__(self, responses: list[object | None]) -> None:
        self.responses = list(responses)
        self.execute_count = 0

    async def execute(self, _statement: object) -> FakeResult:
        if not self.responses:
            message = "unexpected extra session.execute call"
            raise AssertionError(message)
        self.execute_count += 1
        return FakeResult(self.responses.pop(0))


def _prompt(*, asset: manifest.PromptAsset) -> object:
    return type(
        "PromptRow",
        (),
        {
            "call_type": asset.call_type,
            "compatible_schema_version_id": asset.compatible_schema_version_id,
            "content": "prompt",
            "id": asset.id,
            "output_schema_version_id": asset.output_schema_version_id,
            "sha256": asset.sha256,
        },
    )()


def _schema(*, asset: manifest.RequirementSchemaAsset) -> object:
    return type(
        "SchemaRow",
        (),
        {
            "id": asset.id,
            "schema_id": asset.schema_id,
            "sha256": asset.sha256,
        },
    )()


def _search_schema() -> object:
    asset = manifest.SEARCH_INTERPRETATION_SCHEMA_V1
    return type(
        "SearchSchemaRow",
        (),
        {
            "id": asset.id,
            "schema_id": asset.schema_id,
            "sha256": asset.sha256,
        },
    )()


@pytest.mark.anyio
async def test_validate_candidate_assets_accepts_prompt_v1_with_schema_v1() -> None:
    prompt = manifest.JOB_REQUIREMENT_PROMPT_V1
    schema = manifest.JOB_REQUIREMENT_SCHEMA_V1
    session = FakeSession([_prompt(asset=prompt), _schema(asset=schema)])

    resolved = await service.validate_candidate_assets(
        cast("AsyncSession", cast("object", session)),
        CandidateConfiguration(model="x-ai/grok-4.5", prompt_version_id=prompt.id),
    )

    parsing = resolved[CALL_TYPE_JOB_REQUIREMENT_PARSING]
    assert parsing.prompt.id == prompt.id
    assert parsing.catalog_schema.id == schema.id
    assert session.execute_count == 2
    assert session.responses == []


@pytest.mark.anyio
async def test_validate_candidate_assets_accepts_prompt_v2_with_schema_v2() -> None:
    prompt = manifest.JOB_REQUIREMENT_PROMPT_V2
    schema = manifest.JOB_REQUIREMENT_SCHEMA_V2
    session = FakeSession([_prompt(asset=prompt), _schema(asset=schema)])

    resolved = await service.validate_candidate_assets(
        cast("AsyncSession", cast("object", session)),
        CandidateConfiguration(model="x-ai/grok-4.5", prompt_version_id=prompt.id),
    )

    parsing = resolved[CALL_TYPE_JOB_REQUIREMENT_PARSING]
    assert parsing.prompt.id == prompt.id
    assert parsing.catalog_schema.id == schema.id
    assert session.execute_count == 2
    assert session.responses == []


@pytest.mark.anyio
async def test_validate_candidate_assets_accepts_declared_call_types() -> None:
    parsing_prompt = manifest.JOB_REQUIREMENT_PROMPT_V2
    parsing_schema = manifest.JOB_REQUIREMENT_SCHEMA_V2
    search_prompt = manifest.SEARCH_INTERPRETATION_PROMPT_V1
    search_catalog = manifest.JOB_REQUIREMENT_SCHEMA_V1
    session = FakeSession(
        [
            _prompt(asset=parsing_prompt),
            _schema(asset=parsing_schema),
            _prompt(asset=search_prompt),
            _schema(asset=search_catalog),
            _search_schema(),
        ]
    )

    resolved = await service.validate_candidate_assets(
        cast("AsyncSession", cast("object", session)),
        CandidateConfiguration(
            model="x-ai/grok-4.5",
            bindings=(
                CallTypeBinding(
                    call_type=CALL_TYPE_JOB_REQUIREMENT_PARSING,
                    prompt_version_id=parsing_prompt.id,
                    request_timeout_seconds=180,
                ),
                CallTypeBinding(
                    call_type=CALL_TYPE_SEARCH_INTERPRETATION,
                    prompt_version_id=search_prompt.id,
                    request_timeout_seconds=15,
                ),
            ),
        ),
    )

    assert set(resolved) == {CALL_TYPE_JOB_REQUIREMENT_PARSING, CALL_TYPE_SEARCH_INTERPRETATION}
    assert session.execute_count == 5
    assert session.responses == []


@pytest.mark.anyio
async def test_validate_candidate_assets_rejects_schema_hash_drift() -> None:
    prompt = manifest.JOB_REQUIREMENT_PROMPT_V2
    schema = manifest.JOB_REQUIREMENT_SCHEMA_V2
    drifted = type(
        "SchemaRow",
        (),
        {
            "id": schema.id,
            "schema_id": schema.schema_id,
            "sha256": "0" * 64,
        },
    )()
    session = FakeSession([_prompt(asset=prompt), drifted])

    with pytest.raises(service.IncompatibleLlmAssetsError):
        _ = await service.validate_candidate_assets(
            cast("AsyncSession", cast("object", session)),
            CandidateConfiguration(model="x-ai/grok-4.5", prompt_version_id=prompt.id),
        )


@pytest.mark.anyio
async def test_validate_candidate_assets_rejects_call_type_mismatch() -> None:
    prompt = manifest.JOB_REQUIREMENT_PROMPT_V1
    session = FakeSession([])

    with pytest.raises(service.IncompatibleLlmAssetsError):
        _ = await service.validate_candidate_assets(
            cast("AsyncSession", cast("object", session)),
            CandidateConfiguration(
                model="x-ai/grok-4.5",
                bindings=(
                    CallTypeBinding(
                        call_type=CALL_TYPE_SEARCH_INTERPRETATION,
                        prompt_version_id=prompt.id,
                        request_timeout_seconds=15,
                    ),
                    CallTypeBinding(
                        call_type=CALL_TYPE_JOB_REQUIREMENT_PARSING,
                        prompt_version_id=prompt.id,
                        request_timeout_seconds=180,
                    ),
                ),
            ),
        )
