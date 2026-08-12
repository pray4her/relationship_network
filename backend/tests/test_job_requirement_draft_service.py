# ruff: noqa: RUF001

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import UTC, datetime
from typing import cast

import pytest

from relationship_network_api.job_requirement_draft_service import (
    merge_editable_requirement_document,
)
from relationship_network_api.job_requirement_validation import (
    INVALID_BUSINESS_RULE,
    RequirementResultValidationError,
    build_editable_requirement_document,
    confirmability_errors,
    validate_editable_requirement_document,
)
from relationship_network_api.llm_assets import manifest

DRAFT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
ACTOR_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
CHANGED_AT = datetime(2026, 8, 11, 9, 30, tzinfo=UTC)


def evidence(source_id: str, text: str, quote: str) -> dict[str, object]:
    start = text.index(quote)
    return {
        "source_id": source_id,
        "start_offset": start,
        "end_offset": start + len(quote),
        "quote": quote,
    }


def model_result(*, with_conflict: bool = True) -> dict[str, object]:
    description = "需要海外华人，H 指数至少 30。"
    material = "华人身份不限，优先人工智能研究。"
    conflicts: list[dict[str, object]] = []
    if with_conflict:
        conflicts.append(
            {
                "description": "华人身份来源冲突",
                "evidence": [
                    evidence("job-description", description, "海外华人"),
                    evidence("job-material:1", material, "华人身份不限"),
                ],
            }
        )
    return {
        "hard_conditions": [
            {
                "field": "h_index",
                "operator": "gte",
                "value": 30,
                "description": "H 指数至少 30",
                "evidence": [evidence("job-description", description, "H 指数至少 30")],
            }
        ],
        "preference_conditions": [],
        "research_topic_query": "  人工智能  ",
        "unsupported_conditions": [
            {
                "description": "有创业经验",
                "evidence": [evidence("job-material:1", material, "人工智能研究")],
            }
        ],
        "source_conflicts": conflicts,
    }


def editable_document() -> dict[str, object]:
    document = build_editable_requirement_document(model_result(), draft_id=DRAFT_ID)
    return validate_editable_requirement_document(
        document,
        schema=manifest.read_requirement_editor_schema(manifest.JOB_REQUIREMENT_SCHEMA_V2.id),
        asset=manifest.JOB_REQUIREMENT_SCHEMA_V2,
        source_texts={
            "job-description": "需要海外华人，H 指数至少 30。",
            "job-material:1": "华人身份不限，优先人工智能研究。",
        },
    )


def submission(document: dict[str, object]) -> dict[str, object]:
    def condition(item: dict[str, object]) -> dict[str, object]:
        return {
            "item_id": item["item_id"],
            "field": item["field"],
            "operator": item["operator"],
            "value": deepcopy(item["value"]),
            "description": item["description"],
        }

    return {
        "hard_conditions": [
            condition(item) for item in cast("list[dict[str, object]]", document["hard_conditions"])
        ],
        "preference_conditions": [
            condition(item)
            for item in cast("list[dict[str, object]]", document["preference_conditions"])
        ],
        "research_topic_query": cast("dict[str, object]", document["research_topic_query"])[
            "value"
        ],
        "unsupported_conditions": [
            {"item_id": item["item_id"], "description": item["description"]}
            for item in cast("list[dict[str, object]]", document["unsupported_conditions"])
        ],
        "source_conflicts": [
            {"item_id": item["item_id"], "resolution_note": None}
            for item in cast("list[dict[str, object]]", document["source_conflicts"])
        ],
    }


def test_model_output_is_enriched_without_changing_the_frozen_schema_asset() -> None:
    document = editable_document()
    hard = cast("list[dict[str, object]]", document["hard_conditions"])[0]
    model_hard = cast("list[dict[str, object]]", model_result()["hard_conditions"])[0]
    query = cast("dict[str, object]", document["research_topic_query"])

    assert hard["origin"] == "model"
    assert hard["model_snapshot"] == model_hard
    assert hard["last_modified_by"] is None
    assert query == {
        "value": "人工智能",
        "model_value": "  人工智能  ",
        "last_modified_by": None,
        "last_modified_at": None,
    }


def test_merge_preserves_model_provenance_and_user_added_items_claim_no_evidence() -> None:
    document = editable_document()
    submitted = submission(document)
    submitted_hard = cast("list[dict[str, object]]", submitted["hard_conditions"])
    original = submitted_hard[0]
    original["value"] = 35
    original["description"] = "H 指数至少 35"
    cast("list[object]", submitted["hard_conditions"]).clear()
    cast("list[object]", submitted["preference_conditions"]).extend(
        [
            original,
            {
                "item_id": None,
                "field": "country",
                "operator": "in",
                "value": [" 中国 ", "美国", "中国"],
                "description": "  优先中国或美国  ",
            },
        ]
    )
    submitted["research_topic_query"] = "  医疗人工智能  "

    merged = merge_editable_requirement_document(
        document,
        submitted,
        actor_user_id=ACTOR_ID,
        changed_at=CHANGED_AT,
    )
    validated = validate_editable_requirement_document(
        merged,
        schema=manifest.read_requirement_editor_schema(manifest.JOB_REQUIREMENT_SCHEMA_V2.id),
        asset=manifest.JOB_REQUIREMENT_SCHEMA_V2,
    )
    preferences = cast("list[dict[str, object]]", validated["preference_conditions"])
    modified, added = preferences

    assert modified["origin"] == "model"
    assert cast("dict[str, object]", modified["model_snapshot"])["value"] == 30
    assert modified["evidence"]
    assert modified["last_modified_by"] == str(ACTOR_ID)
    assert added["origin"] == "user_added"
    assert added["value"] == ["中国", "美国"]
    assert added["evidence"] == []
    assert added["model_snapshot"] is None
    assert cast("dict[str, object]", validated["research_topic_query"])["value"] == "医疗人工智能"


def test_deletion_moves_the_complete_fact_to_server_owned_removed_history() -> None:
    document = editable_document()
    submitted = submission(document)
    cast("list[object]", submitted["hard_conditions"]).clear()
    cast("list[object]", submitted["unsupported_conditions"]).clear()

    merged = merge_editable_requirement_document(
        document,
        submitted,
        actor_user_id=ACTOR_ID,
        changed_at=CHANGED_AT,
    )
    removed = cast("list[dict[str, object]]", merged["removed_facts"])

    assert {item["kind"] for item in removed} == {"hard_condition", "unsupported_condition"}
    assert all(item["removed_by"] == str(ACTOR_ID) for item in removed)
    assert all(item["model_snapshot"] is not None for item in removed)


def test_conflict_requires_a_note_and_can_be_reopened_without_losing_original_evidence() -> None:
    document = editable_document()
    submitted = submission(document)
    conflict_input = cast("list[dict[str, object]]", submitted["source_conflicts"])[0]
    conflict_input["resolution_note"] = "  以职位描述为准  "
    resolved = merge_editable_requirement_document(
        document,
        submitted,
        actor_user_id=ACTOR_ID,
        changed_at=CHANGED_AT,
    )
    assert confirmability_errors(resolved) == ()
    conflict = cast("list[dict[str, object]]", resolved["source_conflicts"])[0]
    assert cast("dict[str, object]", conflict["resolution"])["note"] == "以职位描述为准"
    assert (
        conflict["model_snapshot"]
        == cast("list[dict[str, object]]", document["source_conflicts"])[0]["model_snapshot"]
    )

    reopened_submission = submission(resolved)
    reopened = merge_editable_requirement_document(
        resolved,
        reopened_submission,
        actor_user_id=ACTOR_ID,
        changed_at=CHANGED_AT,
    )
    assert confirmability_errors(reopened) == ("source_conflicts_unresolved",)


@pytest.mark.parametrize(
    ("field", "operator", "value"),
    [
        ("h_index", "eq", 10),
        ("h_index", "between", [20, 10]),
        ("chinese_identity", "eq", "未知身份"),
        ("country", "match", "中国"),
        ("current_affiliation", "in", ["清华大学"]),
    ],
)
def test_editor_rejects_field_operator_and_value_combinations(
    field: str,
    operator: str,
    value: object,
) -> None:
    document = editable_document()
    submitted = submission(document)
    condition = cast("list[dict[str, object]]", submitted["hard_conditions"])[0]
    condition.update({"field": field, "operator": operator, "value": value})

    def merge_and_validate() -> None:
        merged = merge_editable_requirement_document(
            document,
            submitted,
            actor_user_id=ACTOR_ID,
            changed_at=CHANGED_AT,
        )
        _ = validate_editable_requirement_document(
            merged,
            schema=manifest.read_requirement_editor_schema(manifest.JOB_REQUIREMENT_SCHEMA_V2.id),
            asset=manifest.JOB_REQUIREMENT_SCHEMA_V2,
        )

    with pytest.raises(RequirementResultValidationError) as captured:
        merge_and_validate()
    assert captured.value.category == INVALID_BUSINESS_RULE
