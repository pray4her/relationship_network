# ruff: noqa: RUF001

"""Unit coverage for requirement version confirmability checks."""

from __future__ import annotations

import uuid

from relationship_network_api.job_requirement_validation import (
    build_editable_requirement_document,
    confirmability_errors,
    validate_editable_requirement_document,
)
from relationship_network_api.llm_assets import manifest

DRAFT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")


def evidence(source_id: str, text: str, quote: str) -> dict[str, object]:
    start = text.index(quote)
    return {
        "source_id": source_id,
        "start_offset": start,
        "end_offset": start + len(quote),
        "quote": quote,
    }


def model_result(*, with_conflict: bool = False) -> dict[str, object]:
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
        "research_topic_query": "人工智能",
        "unsupported_conditions": [],
        "source_conflicts": conflicts,
    }


def editable_document(*, with_conflict: bool = False) -> dict[str, object]:
    document = build_editable_requirement_document(
        model_result(with_conflict=with_conflict),
        draft_id=DRAFT_ID,
    )
    return validate_editable_requirement_document(
        document,
        schema=manifest.read_requirement_editor_schema(manifest.JOB_REQUIREMENT_SCHEMA_V2.id),
        asset=manifest.JOB_REQUIREMENT_SCHEMA_V2,
    )


def test_confirmability_errors_block_unresolved_conflicts() -> None:
    document = editable_document(with_conflict=True)
    assert confirmability_errors(document) == ("source_conflicts_unresolved",)


def test_confirmability_errors_block_empty_research_topic() -> None:
    document = editable_document()
    query = document["research_topic_query"]
    assert isinstance(query, dict)
    query["value"] = "   "
    assert confirmability_errors(document) == ("research_topic_query_empty",)


def test_confirmability_errors_pass_for_ready_document() -> None:
    document = editable_document()
    assert confirmability_errors(document) == ()
