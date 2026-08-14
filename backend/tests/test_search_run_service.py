"""Unit tests for the natural-language search run service's pure helpers."""

from __future__ import annotations

import uuid

import pytest

from relationship_network_api import search_run_service as service
from relationship_network_api.search_base_contract import HardCondition

CONFIG_ID = uuid.UUID("66666666-6666-4666-8666-666666666666")


def test_normalize_utterance_applies_nfc_and_lf() -> None:
    raw = "café\r\n研究\r人才"
    normalized = service.normalize_utterance(raw)
    assert "\r\n" not in normalized
    assert "\r" not in normalized
    # NFC composed: e + combining acute (U+0301) becomes é.
    assert "́" not in normalized
    assert "café" in normalized


def test_validate_utterance_accepts_within_limit() -> None:
    assert service.validate_utterance("  找 AI 研究员  ") == "  找 AI 研究员  "


def test_validate_utterance_rejects_empty_and_blank() -> None:
    with pytest.raises(service.InvalidUtteranceError):
        _ = service.validate_utterance("")
    with pytest.raises(service.InvalidUtteranceError):
        _ = service.validate_utterance("   \n  ")


def test_validate_utterance_rejects_over_limit() -> None:
    with pytest.raises(service.InvalidUtteranceError):
        _ = service.validate_utterance("人" * (service.MAX_UTTERANCE_CHARACTERS + 1))


def test_idempotency_fingerprint_is_stable_and_sensitive() -> None:
    base = service._idempotency_fingerprint("query", CONFIG_ID, "v1")
    assert base == service._idempotency_fingerprint("query", CONFIG_ID, "v1")
    assert base != service._idempotency_fingerprint("query2", CONFIG_ID, "v1")
    assert base != service._idempotency_fingerprint("query", CONFIG_ID, "v2")
    assert base != service._idempotency_fingerprint("query", uuid.uuid4(), "v1")


def test_hard_conditions_strips_description_and_maps_values() -> None:
    interpretation: dict[str, object] = {
        "hard_conditions": [
            {
                "field": "h_index",
                "operator": "gte",
                "value": 10,
                "description": "h-index 至少 10",
            },
            {
                "field": "country",
                "operator": "in",
                "value": ["US", "CN"],
                "description": "国家",
            },
        ],
        "research_topic_query": "condensed matter",
        "unsupported_conditions": [{"description": "需要奖项"}],
    }
    conditions = service._hard_conditions(interpretation)
    assert conditions == (
        HardCondition(field="h_index", operator="gte", value=10),
        HardCondition(field="country", operator="in", value=["US", "CN"]),
    )


def test_hard_conditions_ignores_malformed_entries() -> None:
    interpretation: dict[str, object] = {
        "hard_conditions": [
            {"field": "h_index", "operator": "gte", "value": 5},
            "not-a-dict",
            {"operator": "eq", "value": "x"},
        ],
        "research_topic_query": "",
        "unsupported_conditions": [],
    }
    assert service._hard_conditions(interpretation) == (
        HardCondition(field="h_index", operator="gte", value=5),
    )


def test_hard_conditions_empty_when_missing() -> None:
    assert service._hard_conditions({"research_topic_query": "x"}) == ()  # type: ignore[arg-type]


def test_resolve_sort_defaults_and_validates() -> None:
    assert service._resolve_sort(None) == service.SORT_KEY_SEMANTIC
    assert service._resolve_sort("h_index") == "h_index"
    for key in service.SORT_KEYS:
        assert service._resolve_sort(key) == key
    with pytest.raises(service.InvalidSortError):
        _ = service._resolve_sort("not_a_sort_key")


def test_order_by_for_sort_returns_two_clauses() -> None:
    for key in (*service.SORT_KEYS, service.SORT_KEY_SEMANTIC):
        clauses = service._order_by_for_sort(key)
        assert len(clauses) == 2
    with pytest.raises(service.InvalidSortError):
        _ = service._order_by_for_sort("bogus")


def test_parse_cursor() -> None:
    assert service._parse_cursor(None) == 0
    assert service._parse_cursor("0") == 0
    assert service._parse_cursor("50") == 50
    assert service._parse_cursor("-3") == 0
    assert service._parse_cursor("not-int") == 0


def test_error_details_are_stable() -> None:
    assert service.InvalidUtteranceError().detail == "invalid_utterance"
    assert (
        service.SearchIdempotencyConflictError().detail
        == "search_idempotency_fingerprint_conflict"
    )
    assert service.SearchCreationRateLimitedError().detail == "search_creation_rate_limited"
    assert service.SearchInProgressError().detail == "search_in_progress"
    assert service.SearchQuotaExceededError(uuid.uuid4()).detail == "search_quota_exceeded"
    assert service.SearchRunNotFoundError().detail == "search_run_not_found"
    assert service.InvalidSortError().detail == "invalid_sort"
