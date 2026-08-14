import secrets

from _pytest.monkeypatch import MonkeyPatch

from relationship_network_api import llm_configuration_worker as worker
from relationship_network_api.llm_assets.manifest import (
    CALL_TYPE_JOB_REQUIREMENT_PARSING,
    CALL_TYPE_SEARCH_INTERPRETATION,
)
from relationship_network_api.openrouter import CallTypeBinding, CandidateConfiguration

SCHEMA: dict[str, object] = {"type": "object"}


def candidate() -> CandidateConfiguration:
    return CandidateConfiguration(
        model="x-ai/grok-4.5",
        bindings=(
            CallTypeBinding(
                call_type=CALL_TYPE_JOB_REQUIREMENT_PARSING,
                prompt_version_id="job-requirement-prompt-v1",
                request_timeout_seconds=180,
            ),
            CallTypeBinding(
                call_type=CALL_TYPE_SEARCH_INTERPRETATION,
                prompt_version_id="search-interpretation-prompt-v1",
                request_timeout_seconds=15,
            ),
        ),
    )


def test_retry_backoff_is_bounded_and_jittered(monkeypatch: MonkeyPatch) -> None:
    def fixed_jitter(_upper: int) -> int:
        return 1

    monkeypatch.setattr(secrets, "randbelow", fixed_jitter)

    assert worker.retry_delay_seconds(1) == 3
    assert worker.retry_delay_seconds(2) == 5
    assert worker.retry_delay_seconds(20) == 31


def test_probe_request_hash_is_stable_and_contains_no_api_key() -> None:
    first = worker._probe_request_hash(
        candidate(),
        call_type=CALL_TYPE_JOB_REQUIREMENT_PARSING,
        system_prompt="system",
        schema=SCHEMA,
    )
    second = worker._probe_request_hash(
        candidate(),
        call_type=CALL_TYPE_JOB_REQUIREMENT_PARSING,
        system_prompt="system",
        schema=SCHEMA,
    )
    search = worker._probe_request_hash(
        candidate(),
        call_type=CALL_TYPE_SEARCH_INTERPRETATION,
        system_prompt="system",
        schema=SCHEMA,
    )

    assert first == second
    assert first != search
    assert len(first) == 64
    assert "not-persisted" not in first
    assert "not-persisted" not in search
