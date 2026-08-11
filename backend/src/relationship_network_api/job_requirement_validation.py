from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, cast, final

from jsonschema import Draft202012Validator

if TYPE_CHECKING:
    from relationship_network_api.llm_assets.manifest import RequirementSchemaAsset

INVALID_SCHEMA: Final = "invalid_schema"
INVALID_BUSINESS_RULE: Final = "invalid_business_rule"
INVALID_EVIDENCE: Final = "invalid_evidence"
MIN_CONFLICT_SOURCES: Final = 2

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]


@final
class RequirementResultValidationError(ValueError):
    def __init__(self, category: str, detail: str) -> None:
        super().__init__(detail)
        self.category = category


@final
@dataclass(frozen=True)
class NormalizedSource:
    source_id: str
    sent_text: str


def normalize_sent_text(value: str) -> str:
    """Apply only the source-coordinate normalization approved by ADR 0005."""
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def snapshot_content_sha256(sources: list[NormalizedSource]) -> str:
    payload = [{"content": source.sent_text, "source_id": source.source_id} for source in sources]
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return sha256_text(serialized)


def validate_requirement_result(
    value: object,
    *,
    schema: dict[str, object],
    asset: RequirementSchemaAsset,
    source_texts: dict[str, str],
) -> dict[str, object]:
    """Validate the complete result before any draft row can be created."""
    errors = sorted(
        Draft202012Validator(schema).iter_errors(cast("JsonValue", value)),
        key=lambda error: list(error.path),
    )
    if errors:
        first = errors[0]
        path = ".".join(str(part) for part in first.absolute_path) or "$"
        raise RequirementResultValidationError(INVALID_SCHEMA, f"{path}: {first.message}")
    result = cast("dict[str, object]", value)
    hard = _object_list(result["hard_conditions"])
    preferences = _object_list(result["preference_conditions"])
    unsupported = _object_list(result["unsupported_conditions"])
    conflicts = _object_list(result["source_conflicts"])
    combined_limit = asset.output_limits["combined_conditions"]
    if len(hard) + len(preferences) + len(unsupported) > combined_limit:
        raise RequirementResultValidationError(
            INVALID_BUSINESS_RULE,
            "combined condition limit exceeded",
        )
    query = cast("str", result["research_topic_query"])
    if not query.strip():
        raise RequirementResultValidationError(
            INVALID_BUSINESS_RULE,
            "research_topic_query must remain non-empty after trimming",
        )
    for condition in [*hard, *preferences]:
        _validate_executable_condition(condition, asset)
        _ = _validate_evidence_list(condition["evidence"], source_texts)
    for item in unsupported:
        _ = _validate_evidence_list(item["evidence"], source_texts)
    for conflict in conflicts:
        evidence = _validate_evidence_list(conflict["evidence"], source_texts)
        if len({cast("str", item["source_id"]) for item in evidence}) < MIN_CONFLICT_SOURCES:
            raise RequirementResultValidationError(
                INVALID_BUSINESS_RULE,
                "source conflict must reference at least two distinct sources",
            )
    return result


def _object_list(value: object) -> list[dict[str, object]]:
    return [cast("dict[str, object]", item) for item in cast("list[object]", value)]


def _validate_executable_condition(
    condition: dict[str, object],
    asset: RequirementSchemaAsset,
) -> None:
    field = cast("str", condition["field"])
    operator = cast("str", condition["operator"])
    operators = asset.field_catalog.get(field)
    if operators is None or operator not in operators:
        raise RequirementResultValidationError(
            INVALID_BUSINESS_RULE,
            "condition field and operator are incompatible",
        )
    value = condition["value"]
    if field in {"qs_top200_rank", "world_top500_rank", "h_index", "total_citations"}:
        if operator == "between":
            bounds = cast("list[float | int]", value)
            if bounds[0] > bounds[1]:
                raise RequirementResultValidationError(
                    INVALID_BUSINESS_RULE,
                    "between bounds must be ordered",
                )
        elif not isinstance(value, (int, float)) or isinstance(value, bool):
            raise RequirementResultValidationError(INVALID_BUSINESS_RULE, "numeric value required")
    if field == "chinese_identity":
        allowed = set(asset.chinese_identity_values)
        values = [value] if operator == "eq" else cast("list[object]", value)
        if any(item not in allowed for item in values):
            raise RequirementResultValidationError(
                INVALID_BUSINESS_RULE,
                "invalid chinese_identity value",
            )


def _validate_evidence_list(
    value: object,
    source_texts: dict[str, str],
) -> list[dict[str, object]]:
    evidence = _object_list(value)
    for item in evidence:
        source_id = cast("str", item["source_id"])
        source = source_texts.get(source_id)
        if source is None:
            raise RequirementResultValidationError(
                INVALID_EVIDENCE,
                "evidence source does not exist in the frozen snapshot",
            )
        start = cast("int", item["start_offset"])
        end = cast("int", item["end_offset"])
        quote = cast("str", item["quote"])
        if start < 0 or end <= start or end > len(source):
            raise RequirementResultValidationError(
                INVALID_EVIDENCE, "evidence offset is out of range"
            )
        if source[start:end] != quote:
            raise RequirementResultValidationError(
                INVALID_EVIDENCE,
                "evidence quote does not exactly match the normalized source slice",
            )
    return evidence
