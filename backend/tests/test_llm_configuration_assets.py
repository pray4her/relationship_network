from typing import TYPE_CHECKING, cast, final

import pytest

from relationship_network_api import llm_configuration_service as service
from relationship_network_api.llm_assets import manifest
from relationship_network_api.openrouter import CandidateConfiguration

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
            "id": asset.id,
            "compatible_schema_version_id": asset.compatible_schema_version_id,
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


@pytest.mark.anyio
async def test_validate_candidate_assets_accepts_prompt_v1_with_schema_v1() -> None:
    prompt = manifest.JOB_REQUIREMENT_PROMPT_V1
    schema = manifest.JOB_REQUIREMENT_SCHEMA_V1
    session = FakeSession([_prompt(asset=prompt), _schema(asset=schema)])

    resolved_prompt, resolved_schema = await service.validate_candidate_assets(
        cast("AsyncSession", cast("object", session)),
        CandidateConfiguration(model="x-ai/grok-4.5", prompt_version_id=prompt.id),
    )

    assert resolved_prompt.id == prompt.id
    assert resolved_schema.id == schema.id
    assert session.execute_count == 2
    assert session.responses == []


@pytest.mark.anyio
async def test_validate_candidate_assets_accepts_prompt_v2_with_schema_v2() -> None:
    prompt = manifest.JOB_REQUIREMENT_PROMPT_V2
    schema = manifest.JOB_REQUIREMENT_SCHEMA_V2
    session = FakeSession([_prompt(asset=prompt), _schema(asset=schema)])

    resolved_prompt, resolved_schema = await service.validate_candidate_assets(
        cast("AsyncSession", cast("object", session)),
        CandidateConfiguration(model="x-ai/grok-4.5", prompt_version_id=prompt.id),
    )

    assert resolved_prompt.id == prompt.id
    assert resolved_schema.id == schema.id
    assert session.execute_count == 2
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
