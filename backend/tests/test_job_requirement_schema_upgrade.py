"""Unit coverage for deterministic schema upgrades and asset readiness checks."""

from __future__ import annotations

from copy import deepcopy
from typing import cast

import pytest

from relationship_network_api import job_requirement_service, job_requirement_worker
from relationship_network_api.job_requirement_schema_upgrade import (
    CONVERTER_V1_TO_V2,
    convert_document,
    converter_version_for,
)
from relationship_network_api.llm_assets import manifest
from relationship_network_api.models import (
    JobRequirementSchemaVersion,
    LlmConfigurationVersion,
    PromptVersion,
)

SCHEMA_V1 = manifest.JOB_REQUIREMENT_SCHEMA_V1.id
SCHEMA_V2 = manifest.JOB_REQUIREMENT_SCHEMA_V2.id
PROMPT_V1 = manifest.JOB_REQUIREMENT_PROMPT_V1.id
PROMPT_V2 = manifest.JOB_REQUIREMENT_PROMPT_V2.id


def condition(item_id: str, field: str, operator: str, value: object) -> dict[str, object]:
    return {
        "item_id": item_id,
        "field": field,
        "operator": operator,
        "value": value,
        "description": f"描述 {item_id}",
        "evidence": [],
        "origin": "model",
        "model_snapshot": None,
    }


def document() -> dict[str, object]:
    return {
        "hard_conditions": [
            condition("hard-1", "h_index", "gte", 30),
            condition("hard-2", "chinese_identity", "eq", "海外华人"),
        ],
        "preference_conditions": [
            condition("pref-1", "chinese_identity", "in", ["国内华人", "海外华人"]),
            condition("pref-2", "country", "in", ["中国"]),
        ],
        "research_topic_query": {"value": "人工智能"},
        "unsupported_conditions": [],
        "source_conflicts": [],
        "removed_facts": [],
    }


def test_lossless_conversion_preserves_every_field_item_and_order() -> None:
    source = document()
    before = deepcopy(source)

    conversion = convert_document(source, from_schema_id=SCHEMA_V1, to_schema_id=SCHEMA_V2)

    assert source == before
    assert conversion.document == before
    assert conversion.document is not source
    assert conversion.lossy_items == []
    assert conversion.item_mappings == [
        {"item_id": "hard-1", "kind": "hard_condition", "mapping": "copied", "lossless": True},
        {"item_id": "hard-2", "kind": "hard_condition", "mapping": "copied", "lossless": True},
        {
            "item_id": "pref-1",
            "kind": "preference_condition",
            "mapping": "copied",
            "lossless": True,
        },
        {
            "item_id": "pref-2",
            "kind": "preference_condition",
            "mapping": "copied",
            "lossless": True,
        },
    ]


def test_out_of_catalog_chinese_identity_eq_value_is_lossy() -> None:
    source = document()
    hard_conditions = cast("list[dict[str, object]]", source["hard_conditions"])
    lossy_item = hard_conditions[1]
    lossy_item["value"] = "未知身份"
    before = deepcopy(lossy_item)

    conversion = convert_document(source, from_schema_id=SCHEMA_V1, to_schema_id=SCHEMA_V2)

    converted_hard = conversion.document["hard_conditions"]
    assert isinstance(converted_hard, list)
    assert [item["item_id"] for item in converted_hard] == ["hard-1"]
    assert conversion.item_mappings[1] == {
        "item_id": "hard-2",
        "kind": "hard_condition",
        "mapping": "unconvertible_chinese_identity",
        "lossless": False,
    }
    assert conversion.lossy_items == [
        {"item_id": "hard-2", "kind": "hard_condition", "snapshot": before}
    ]


@pytest.mark.parametrize(
    "value",
    [
        ["海外华人", "未知身份"],
        ["国内华人", "海外华人", "外国人", "未知身份"],
        ["国内华人", "海外华人", "外国人", "国内华人"],
    ],
    ids=["out-of-catalog-entry", "longer-than-catalog", "longer-than-catalog-without-dupes-check"],
)
def test_out_of_catalog_or_oversized_chinese_identity_in_list_is_lossy(value: object) -> None:
    source = document()
    preferences = cast("list[dict[str, object]]", source["preference_conditions"])
    lossy_item = preferences[0]
    lossy_item["value"] = value
    before = deepcopy(lossy_item)

    conversion = convert_document(source, from_schema_id=SCHEMA_V1, to_schema_id=SCHEMA_V2)

    converted_preferences = conversion.document["preference_conditions"]
    assert isinstance(converted_preferences, list)
    assert [item["item_id"] for item in converted_preferences] == ["pref-2"]
    assert conversion.item_mappings[2] == {
        "item_id": "pref-1",
        "kind": "preference_condition",
        "mapping": "unconvertible_chinese_identity",
        "lossless": False,
    }
    assert conversion.lossy_items == [
        {"item_id": "pref-1", "kind": "preference_condition", "snapshot": before}
    ]


def test_conversion_is_deterministic() -> None:
    source = document()
    hard_conditions = source["hard_conditions"]
    assert isinstance(hard_conditions, list)
    lossy_item = hard_conditions[1]
    assert isinstance(lossy_item, dict)
    lossy_item["value"] = "未知身份"

    first = convert_document(document(), from_schema_id=SCHEMA_V1, to_schema_id=SCHEMA_V2)
    second = convert_document(document(), from_schema_id=SCHEMA_V1, to_schema_id=SCHEMA_V2)
    first_lossy = convert_document(source, from_schema_id=SCHEMA_V1, to_schema_id=SCHEMA_V2)
    second_lossy = convert_document(source, from_schema_id=SCHEMA_V1, to_schema_id=SCHEMA_V2)

    assert first == second
    assert first_lossy == second_lossy


@pytest.mark.parametrize(
    ("from_schema_id", "to_schema_id", "expected"),
    [
        (SCHEMA_V1, SCHEMA_V2, CONVERTER_V1_TO_V2),
        (SCHEMA_V2, SCHEMA_V1, None),
        (SCHEMA_V1, SCHEMA_V1, None),
        (SCHEMA_V2, SCHEMA_V2, None),
        ("job-requirement-schema-v99", SCHEMA_V2, None),
        (SCHEMA_V1, "job-requirement-schema-v99", None),
    ],
)
def test_converter_version_for_only_knows_registered_pairs(
    from_schema_id: str,
    to_schema_id: str,
    expected: str | None,
) -> None:
    assert converter_version_for(from_schema_id, to_schema_id) == expected


def test_convert_document_rejects_pairs_without_a_registered_converter() -> None:
    with pytest.raises(ValueError, match="no deterministic converter"):
        _ = convert_document(document(), from_schema_id=SCHEMA_V2, to_schema_id=SCHEMA_V1)


def configuration(prompt_id: str, schema_id: str) -> LlmConfigurationVersion:
    return LlmConfigurationVersion(
        prompt_version_id=prompt_id,
        requirement_schema_version_id=schema_id,
    )


@pytest.mark.parametrize(
    ("prompt_id", "schema_id", "expected"),
    [
        (PROMPT_V2, SCHEMA_V2, True),
        (PROMPT_V2, SCHEMA_V1, False),
        (PROMPT_V1, SCHEMA_V2, False),
        (PROMPT_V1, SCHEMA_V1, False),
        ("job-requirement-prompt-v99", SCHEMA_V2, False),
        (PROMPT_V2, "job-requirement-schema-v99", False),
    ],
    ids=[
        "v2-prompt-with-v2-schema",
        "v2-prompt-with-v1-schema",
        "v1-prompt-with-v2-schema",
        "v1-prompt-with-v1-schema-without-editor",
        "unknown-prompt",
        "unknown-schema",
    ],
)
def test_configuration_ready_requires_compatible_deployed_assets_with_editor(
    prompt_id: str,
    schema_id: str,
    *,
    expected: bool,
) -> None:
    assert job_requirement_service._configuration_ready(configuration(prompt_id, schema_id)) is (
        expected
    )


def prompt_asset(
    asset: manifest.PromptAsset = manifest.JOB_REQUIREMENT_PROMPT_V2,
    **overrides: object,
) -> PromptVersion:
    values: dict[str, object] = {
        "id": asset.id,
        "compatible_schema_version_id": asset.compatible_schema_version_id,
        "sha256": asset.sha256,
    }
    values.update(overrides)
    return PromptVersion(**values)  # type: ignore[arg-type]


def schema_asset(
    asset: manifest.RequirementSchemaAsset = manifest.JOB_REQUIREMENT_SCHEMA_V2,
    **overrides: object,
) -> JobRequirementSchemaVersion:
    editor_schema_json = (
        None if asset.editor_path is None else manifest.read_requirement_editor_schema(asset.id)
    )
    values: dict[str, object] = {
        "id": asset.id,
        "sha256": asset.sha256,
        "editor_schema_id": asset.editor_schema_id,
        "editor_sha256": asset.editor_sha256,
        "editor_schema_json": editor_schema_json,
    }
    values.update(overrides)
    return JobRequirementSchemaVersion(**values)  # type: ignore[arg-type]


def test_assets_match_accepts_the_deployed_v2_pair() -> None:
    assert job_requirement_worker._assets_match(prompt=prompt_asset(), schema=schema_asset())


@pytest.mark.parametrize(
    ("prompt", "schema"),
    [
        (prompt_asset(), schema_asset(manifest.JOB_REQUIREMENT_SCHEMA_V1)),
        (
            prompt_asset(manifest.JOB_REQUIREMENT_PROMPT_V1),
            schema_asset(manifest.JOB_REQUIREMENT_SCHEMA_V1),
        ),
        (prompt_asset(id="job-requirement-prompt-v99"), schema_asset()),
        (prompt_asset(), schema_asset(id="job-requirement-schema-v99")),
        (prompt_asset(sha256="0" * 64), schema_asset()),
        (prompt_asset(), schema_asset(sha256="0" * 64)),
        (prompt_asset(), schema_asset(editor_sha256="0" * 64)),
        (prompt_asset(), schema_asset(editor_schema_json={"$id": "drifted"})),
        (prompt_asset(compatible_schema_version_id=SCHEMA_V1), schema_asset()),
    ],
    ids=[
        "v2-prompt-with-v1-schema",
        "v1-pair-without-editor-schema",
        "unknown-prompt",
        "unknown-schema",
        "prompt-hash-drift",
        "schema-hash-drift",
        "editor-hash-drift",
        "editor-schema-drift",
        "prompt-pointer-drift",
    ],
)
def test_assets_match_rejects_mismatched_undeployed_or_drifted_assets(
    prompt: PromptVersion,
    schema: JobRequirementSchemaVersion,
) -> None:
    assert not job_requirement_worker._assets_match(prompt=prompt, schema=schema)
