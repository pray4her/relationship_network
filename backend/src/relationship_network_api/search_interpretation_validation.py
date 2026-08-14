from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast, final

from jsonschema import Draft202012Validator

from relationship_network_api.job_requirement_validation import (
    INVALID_BUSINESS_RULE,
    INVALID_SCHEMA,
    _object_list,
    _validate_executable_condition,
    _validate_nonblank_description,
)

if TYPE_CHECKING:
    from relationship_network_api.llm_assets.manifest import RequirementSchemaAsset

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]

EMPTY_BOTH: Final = "hard_conditions and research_topic_query cannot both be empty"


@final
class SearchInterpretationValidationError(ValueError):
    """Raised when a search interpretation document fails Schema or business rules."""

    def __init__(self, category: str, detail: str) -> None:
        super().__init__(detail)
        self.category = category


def validate_search_interpretation(
    value: object,
    *,
    schema: dict[str, object],
    catalog_asset: RequirementSchemaAsset,
) -> dict[str, object]:
    """Validate a search interpretation document against Schema and catalog rules."""
    errors = sorted(
        Draft202012Validator(schema).iter_errors(cast("JsonValue", value)),
        key=lambda error: list(error.path),
    )
    if errors:
        first = errors[0]
        path = ".".join(str(part) for part in first.absolute_path) or "$"
        raise SearchInterpretationValidationError(INVALID_SCHEMA, f"{path}: {first.message}")
    result = cast("dict[str, object]", value)
    if "preference_conditions" in result or "source_conflicts" in result:
        raise SearchInterpretationValidationError(
            INVALID_BUSINESS_RULE,
            "search interpretation cannot include preference conditions or source conflicts",
        )
    hard = _object_list(result["hard_conditions"])
    unsupported = _object_list(result["unsupported_conditions"])
    combined_limit = catalog_asset.output_limits["combined_conditions"]
    if len(hard) + len(unsupported) > combined_limit:
        raise SearchInterpretationValidationError(
            INVALID_BUSINESS_RULE,
            "combined condition limit exceeded",
        )
    query = cast("str", result["research_topic_query"])
    if not hard and not query.strip():
        raise SearchInterpretationValidationError(INVALID_BUSINESS_RULE, EMPTY_BOTH)
    for condition in hard:
        _validate_nonblank_description(condition)
        _validate_executable_condition(condition, catalog_asset)
    for item in unsupported:
        _validate_nonblank_description(item)
    return result
