from dataclasses import replace
from typing import cast

import pytest
from jsonschema import Draft202012Validator

from relationship_network_api.llm_assets import manifest


def test_deployed_job_requirement_assets_are_hash_verified_and_compatible() -> None:
    manifest.validate_deployed_assets()

    schema = manifest.read_requirement_schema(manifest.JOB_REQUIREMENT_SCHEMA_V1.id)
    prompt = manifest.read_prompt(manifest.JOB_REQUIREMENT_PROMPT_V1.id)

    assert schema["$id"] == "urn:relationship-network:job-requirement-schema:v1"
    assert schema["additionalProperties"] is False
    assert manifest.JOB_REQUIREMENT_PROMPT_V1.compatible_schema_version_id == (
        manifest.JOB_REQUIREMENT_SCHEMA_V1.id
    )
    assert "hard_conditions" in prompt
    assert manifest.JOB_REQUIREMENT_SCHEMA_V1.chinese_identity_values == (
        "国内华人",
        "海外华人",
        "外国人",
    )


def test_v2_schema_uses_closed_condition_objects_and_rejects_extra_fields() -> None:
    schema = manifest.read_requirement_schema(manifest.JOB_REQUIREMENT_SCHEMA_V2.id)
    prompt = manifest.read_prompt(manifest.JOB_REQUIREMENT_PROMPT_V2.id)
    result = {
        "hard_conditions": [
            {
                "field": "h_index",
                "operator": "gte",
                "value": 30,
                "description": "H 指数至少 30",
                "evidence": [
                    {
                        "source_id": "job-description",
                        "start_offset": 0,
                        "end_offset": 2,
                        "quote": "指数",
                    }
                ],
            }
        ],
        "preference_conditions": [],
        "research_topic_query": "人工智能",
        "unsupported_conditions": [],
        "source_conflicts": [],
    }

    validator = Draft202012Validator(schema)
    assert list(validator.iter_errors(result)) == []
    conditions = cast("list[dict[str, object]]", result["hard_conditions"])
    conditions[0]["unexpected"] = True
    assert list(validator.iter_errors(result))
    assert manifest.JOB_REQUIREMENT_PROMPT_V2.compatible_schema_version_id == (
        manifest.JOB_REQUIREMENT_SCHEMA_V2.id
    )
    assert "source_id" in prompt


def test_deployed_asset_validation_rejects_declared_hash_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    drifted = replace(manifest.JOB_REQUIREMENT_SCHEMA_V1, sha256="0" * 64)
    monkeypatch.setattr(manifest, "REQUIREMENT_SCHEMA_ASSETS", (drifted,))

    with pytest.raises(manifest.LlmAssetError, match="hash mismatch"):
        manifest.validate_deployed_assets()


def test_deployed_asset_validation_rejects_duplicate_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset = manifest.JOB_REQUIREMENT_SCHEMA_V1
    monkeypatch.setattr(manifest, "REQUIREMENT_SCHEMA_ASSETS", (asset, asset))

    with pytest.raises(manifest.LlmAssetError, match="duplicate"):
        manifest.validate_deployed_assets()
