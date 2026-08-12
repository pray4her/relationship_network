from __future__ import annotations

import hashlib
import json
import unicodedata
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
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


def build_editable_requirement_document(
    result: dict[str, object],
    *,
    draft_id: uuid.UUID,
) -> dict[str, object]:
    """Add server-owned editing metadata without changing the frozen model output asset."""

    def item_id(kind: str, index: int) -> str:
        return str(uuid.uuid5(draft_id, f"{kind}:{index}"))

    def condition_item(kind: str, index: int, value: dict[str, object]) -> dict[str, object]:
        snapshot = deepcopy(value)
        return {
            "item_id": item_id(kind, index),
            "origin": "model",
            **deepcopy(value),
            "model_snapshot": snapshot,
            "last_modified_by": None,
            "last_modified_at": None,
        }

    def unsupported_item(index: int, value: dict[str, object]) -> dict[str, object]:
        snapshot = deepcopy(value)
        return {
            "item_id": item_id("unsupported", index),
            "origin": "model",
            **deepcopy(value),
            "model_snapshot": snapshot,
            "last_modified_by": None,
            "last_modified_at": None,
        }

    hard = _object_list(result["hard_conditions"])
    preferences = _object_list(result["preference_conditions"])
    unsupported = _object_list(result["unsupported_conditions"])
    conflicts = _object_list(result["source_conflicts"])
    query = cast("str", result["research_topic_query"])
    return {
        "hard_conditions": [
            condition_item("hard", index, value) for index, value in enumerate(hard)
        ],
        "preference_conditions": [
            condition_item("preference", index, value) for index, value in enumerate(preferences)
        ],
        "research_topic_query": {
            "value": query.strip(),
            "model_value": query,
            "last_modified_by": None,
            "last_modified_at": None,
        },
        "unsupported_conditions": [
            unsupported_item(index, value) for index, value in enumerate(unsupported)
        ],
        "source_conflicts": [
            {
                "item_id": item_id("conflict", index),
                **deepcopy(value),
                "model_snapshot": deepcopy(value),
                "resolution": None,
            }
            for index, value in enumerate(conflicts)
        ],
        "removed_facts": [],
    }


def validate_editable_requirement_document(  # noqa: C901, PLR0912, PLR0915
    value: object,
    *,
    schema: dict[str, object],
    asset: RequirementSchemaAsset,
    source_texts: dict[str, str] | None = None,
) -> dict[str, object]:
    """Validate a complete server-owned editable requirement snapshot."""
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
    removed = _object_list(result["removed_facts"])
    if len(hard) + len(preferences) + len(unsupported) > asset.output_limits["combined_conditions"]:
        raise RequirementResultValidationError(
            INVALID_BUSINESS_RULE,
            "combined condition limit exceeded",
        )
    active_ids: set[str] = set()
    for condition in [*hard, *preferences]:
        _validate_item_id(condition, active_ids)
        _validate_editable_origin(condition)
        _validate_nonblank_description(condition)
        _validate_executable_condition(condition, asset)
        if source_texts is not None and condition["evidence"]:
            _ = _validate_evidence_list(condition["evidence"], source_texts)
    for item in unsupported:
        _validate_item_id(item, active_ids)
        _validate_editable_origin(item)
        _validate_nonblank_description(item)
        if source_texts is not None and item["evidence"]:
            _ = _validate_evidence_list(item["evidence"], source_texts)
    query = cast("dict[str, object]", result["research_topic_query"])
    query_value = cast("str", query["value"])
    if not query_value.strip() or query_value != query_value.strip():
        raise RequirementResultValidationError(
            INVALID_BUSINESS_RULE,
            "research_topic_query must be trimmed and non-empty",
        )
    if not cast("str", query["model_value"]).strip():
        raise RequirementResultValidationError(
            INVALID_BUSINESS_RULE,
            "research_topic_query model value must be non-empty",
        )
    for conflict in conflicts:
        _validate_item_id(conflict, active_ids)
        snapshot = cast("dict[str, object]", conflict["model_snapshot"])
        if (
            conflict["description"] != snapshot["description"]
            or conflict["evidence"] != snapshot["evidence"]
        ):
            raise RequirementResultValidationError(
                INVALID_BUSINESS_RULE,
                "source conflict evidence and description are immutable",
            )
        evidence = _object_list(conflict["evidence"])
        if len({cast("str", item["source_id"]) for item in evidence}) < MIN_CONFLICT_SOURCES:
            raise RequirementResultValidationError(
                INVALID_BUSINESS_RULE,
                "source conflict must reference at least two distinct sources",
            )
        if source_texts is not None:
            _ = _validate_evidence_list(conflict["evidence"], source_texts)
        resolution = conflict["resolution"]
        if resolution is not None:
            resolution_object = cast("dict[str, object]", resolution)
            note = cast("str", resolution_object["note"])
            if not note.strip() or note != note.strip():
                raise RequirementResultValidationError(
                    INVALID_BUSINESS_RULE,
                    "source conflict resolution note must be trimmed and non-empty",
                )
            _validate_actor_and_time(
                resolution_object["resolved_by"],
                resolution_object["resolved_at"],
            )
    removed_ids: set[str] = set()
    for fact in removed:
        fact_id = cast("str", fact["item_id"])
        if fact_id in active_ids or fact_id in removed_ids:
            raise RequirementResultValidationError(INVALID_BUSINESS_RULE, "duplicate item_id")
        removed_ids.add(fact_id)
        snapshot = cast("dict[str, object]", fact["removed_snapshot"])
        if snapshot["item_id"] != fact_id or snapshot["origin"] != fact["origin"]:
            raise RequirementResultValidationError(
                INVALID_BUSINESS_RULE,
                "removed fact identity mismatch",
            )
        _validate_actor_and_time(fact["removed_by"], fact["removed_at"])
    return result


def confirmability_errors(value: dict[str, object]) -> tuple[str, ...]:
    """Return the stable checks Issue 06 can reuse before creating a version."""
    errors: list[str] = []
    query = cast("dict[str, object]", value["research_topic_query"])
    if not cast("str", query["value"]).strip():
        errors.append("research_topic_query_empty")
    conflicts = _object_list(value["source_conflicts"])
    if any(conflict["resolution"] is None for conflict in conflicts):
        errors.append("source_conflicts_unresolved")
    return tuple(errors)


def _validate_item_id(item: dict[str, object], seen: set[str]) -> None:
    item_id = cast("str", item["item_id"])
    try:
        _ = uuid.UUID(item_id)
    except ValueError as error:
        raise RequirementResultValidationError(INVALID_BUSINESS_RULE, "invalid item_id") from error
    if item_id in seen:
        raise RequirementResultValidationError(INVALID_BUSINESS_RULE, "duplicate item_id")
    seen.add(item_id)


def _validate_editable_origin(item: dict[str, object]) -> None:
    origin = cast("str", item["origin"])
    model_snapshot = item["model_snapshot"]
    evidence = cast("list[object]", item["evidence"])
    if origin == "model" and (model_snapshot is None or not evidence):
        raise RequirementResultValidationError(
            INVALID_BUSINESS_RULE,
            "model item must preserve its snapshot and evidence",
        )
    if origin == "user_added" and (model_snapshot is not None or evidence):
        raise RequirementResultValidationError(
            INVALID_BUSINESS_RULE,
            "user-added item cannot claim model evidence",
        )


def _validate_nonblank_description(item: dict[str, object]) -> None:
    description = cast("str", item["description"])
    if not description.strip() or description != description.strip():
        raise RequirementResultValidationError(
            INVALID_BUSINESS_RULE,
            "condition description must be trimmed and non-empty",
        )


def _validate_actor_and_time(actor: object, timestamp: object) -> None:
    try:
        _ = uuid.UUID(cast("str", actor))
        _ = datetime.fromisoformat(cast("str", timestamp))
    except (TypeError, ValueError) as error:
        raise RequirementResultValidationError(
            INVALID_BUSINESS_RULE,
            "invalid member or timestamp metadata",
        ) from error


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
