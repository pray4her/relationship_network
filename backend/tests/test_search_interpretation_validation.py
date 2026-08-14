import pytest

from relationship_network_api.llm_assets import manifest
from relationship_network_api.search_interpretation_validation import (
    EMPTY_BOTH,
    SearchInterpretationValidationError,
    validate_search_interpretation,
)


def _valid_document() -> dict[str, object]:
    return {
        "hard_conditions": [
            {
                "description": "H 指数至少 10",
                "field": "h_index",
                "operator": "gte",
                "value": 10,
            }
        ],
        "research_topic_query": "condensed matter",
        "unsupported_conditions": [],
    }


def test_search_interpretation_accepts_hard_conditions_without_topic() -> None:
    document = _valid_document()
    document["research_topic_query"] = ""
    schema = manifest.read_search_interpretation_schema(manifest.SEARCH_INTERPRETATION_SCHEMA_V1.id)
    validated = validate_search_interpretation(
        document,
        schema=schema,
        catalog_asset=manifest.JOB_REQUIREMENT_SCHEMA_V1,
    )
    assert validated["hard_conditions"]


def test_search_interpretation_rejects_dual_empty_and_preference_keys() -> None:
    schema = manifest.read_search_interpretation_schema(manifest.SEARCH_INTERPRETATION_SCHEMA_V1.id)
    empty: dict[str, object] = {
        "hard_conditions": [],
        "research_topic_query": "  ",
        "unsupported_conditions": [],
    }
    with pytest.raises(SearchInterpretationValidationError, match=EMPTY_BOTH):
        _ = validate_search_interpretation(
            empty,
            schema=schema,
            catalog_asset=manifest.JOB_REQUIREMENT_SCHEMA_V1,
        )
    extra = _valid_document()
    extra["preference_conditions"] = []
    with pytest.raises(SearchInterpretationValidationError):
        _ = validate_search_interpretation(
            extra,
            schema=schema,
            catalog_asset=manifest.JOB_REQUIREMENT_SCHEMA_V1,
        )
