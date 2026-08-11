# ruff: noqa: RUF001

from __future__ import annotations

from copy import deepcopy
from typing import cast

import pytest

from relationship_network_api.job_requirement_validation import (
    INVALID_BUSINESS_RULE,
    INVALID_EVIDENCE,
    INVALID_SCHEMA,
    NormalizedSource,
    RequirementResultValidationError,
    normalize_sent_text,
    sha256_text,
    snapshot_content_sha256,
    validate_requirement_result,
)
from relationship_network_api.llm_assets import manifest


def evidence(source_id: str, text: str, quote: str) -> dict[str, object]:
    start = text.index(quote)
    return {
        "source_id": source_id,
        "start_offset": start,
        "end_offset": start + len(quote),
        "quote": quote,
    }


def valid_result() -> dict[str, object]:
    source = "需要海外华人，H指数至少30。"
    return {
        "hard_conditions": [
            {
                "field": "chinese_identity",
                "operator": "eq",
                "value": "海外华人",
                "description": "候选人应为海外华人",
                "evidence": [evidence("job-description", source, "海外华人")],
            }
        ],
        "preference_conditions": [],
        "research_topic_query": "人工智能 AND 医疗",
        "unsupported_conditions": [],
        "source_conflicts": [],
    }


def validate(value: object, *, sources: dict[str, str] | None = None) -> dict[str, object]:
    return validate_requirement_result(
        value,
        schema=manifest.read_requirement_schema(manifest.JOB_REQUIREMENT_SCHEMA_V2.id),
        asset=manifest.JOB_REQUIREMENT_SCHEMA_V2,
        source_texts=sources or {"job-description": "需要海外华人，H指数至少30。"},
    )


def test_sent_text_normalization_is_nfc_and_lf_only() -> None:
    assert normalize_sent_text("Cafe\u0301\r\n A\rB  ") == "Café\n A\nB  "
    assert len(normalize_sent_text("😀e\u0301")) == 2


def test_text_and_snapshot_hashes_are_deterministic_and_order_sensitive() -> None:
    first = NormalizedSource(source_id="job-description", sent_text="职位描述")
    second = NormalizedSource(source_id="job-material:1", sent_text="材料")

    assert sha256_text("职位描述") == sha256_text("职位描述")
    assert snapshot_content_sha256([first, second]) == snapshot_content_sha256([first, second])
    assert snapshot_content_sha256([first, second]) != snapshot_content_sha256([second, first])


def test_v2_accepts_closed_valid_result_and_rejects_extra_condition_property() -> None:
    value = valid_result()
    assert validate(value) == value

    invalid = deepcopy(value)
    condition = cast("list[dict[str, object]]", invalid["hard_conditions"])[0]
    condition["unexpected"] = True
    with pytest.raises(RequirementResultValidationError) as captured:
        _ = validate(invalid)
    assert captured.value.category == INVALID_SCHEMA


def test_research_query_must_remain_non_empty_after_trimming() -> None:
    value = valid_result()
    value["research_topic_query"] = "   "
    with pytest.raises(RequirementResultValidationError) as captured:
        _ = validate(value)
    assert captured.value.category == INVALID_BUSINESS_RULE


def test_between_bounds_must_be_ordered() -> None:
    value = valid_result()
    value["hard_conditions"] = [
        {
            "field": "h_index",
            "operator": "between",
            "value": [30, 10],
            "description": "H 指数范围",
            "evidence": [evidence("job-description", "需要海外华人，H指数至少30。", "H指数至少30")],
        }
    ]
    with pytest.raises(RequirementResultValidationError) as captured:
        _ = validate(value)
    assert captured.value.category == INVALID_BUSINESS_RULE


def test_conflict_must_reference_two_distinct_sources() -> None:
    source = "需要海外华人，H指数至少30。"
    value = valid_result()
    value["source_conflicts"] = [
        {
            "description": "同一来源不能构成冲突",
            "evidence": [
                evidence("job-description", source, "海外华人"),
                evidence("job-description", source, "H指数至少30"),
            ],
        }
    ]
    with pytest.raises(RequirementResultValidationError) as captured:
        _ = validate(value)
    assert captured.value.category == INVALID_BUSINESS_RULE


def test_combined_condition_limit_counts_hard_preferences_and_unsupported() -> None:
    value = valid_result()
    condition = cast("list[dict[str, object]]", value["hard_conditions"])[0]
    value["hard_conditions"] = [deepcopy(condition) for _ in range(100)]
    value["unsupported_conditions"] = [
        {
            "description": "无法执行的条件",
            "evidence": [evidence("job-description", "需要海外华人，H指数至少30。", "海外华人")],
        }
    ]

    with pytest.raises(RequirementResultValidationError) as captured:
        _ = validate(value)
    assert captured.value.category == INVALID_BUSINESS_RULE


@pytest.mark.parametrize("failure", ["unknown", "range", "quote"])
def test_evidence_must_reference_exact_normalized_source_slice(failure: str) -> None:
    value = valid_result()
    condition = cast("list[dict[str, object]]", value["hard_conditions"])[0]
    item = cast("list[dict[str, object]]", condition["evidence"])[0]
    if failure == "unknown":
        item["source_id"] = "job-material:missing"
    elif failure == "range":
        item["end_offset"] = 10_000
    else:
        item["quote"] = "国内华人"

    with pytest.raises(RequirementResultValidationError) as captured:
        _ = validate(value)
    assert captured.value.category == INVALID_EVIDENCE
