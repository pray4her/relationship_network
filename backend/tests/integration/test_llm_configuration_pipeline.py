from __future__ import annotations

import uuid

import pytest

from relationship_network_api.llm_assets import manifest
from relationship_network_api.llm_configuration_worker import process_attempt

from .openrouter_pipeline import (
    Pipeline,
    activate_current_model,
    candidate_attempt_payload,
    divert_platform_outbox,
    enable_ready_configuration,
    ensure_admin,
    finish_attempt,
)


@pytest.mark.anyio
@pytest.mark.integration
async def test_successful_probe_enables_the_candidate(pipeline: Pipeline) -> None:
    attempt = await enable_ready_configuration(pipeline)
    assert attempt["status"] == "succeeded"
    admin = await ensure_admin(pipeline)
    workspace = await admin.get("/admin/llm-configuration")
    assert workspace.status_code == 200
    current = workspace.json()["current"]
    assert current["model"] == "test/success"
    assert current["prompt_version_id"] == manifest.JOB_REQUIREMENT_PROMPT_V2.id
    assert current["request_timeout_seconds"] == 180
    bindings = current["call_bindings"]
    assert bindings["job_requirement_parsing"]["prompt_version_id"] == (
        manifest.JOB_REQUIREMENT_PROMPT_V2.id
    )
    assert bindings["search_interpretation"]["prompt_version_id"] == (
        manifest.SEARCH_INTERPRETATION_PROMPT_V1.id
    )
    assert bindings["search_interpretation"]["request_timeout_seconds"] == 15


@pytest.mark.anyio
@pytest.mark.integration
async def test_invalid_structure_probe_fails_without_replacing_current(
    pipeline: Pipeline,
) -> None:
    first = await enable_ready_configuration(pipeline)
    assert first["status"] == "succeeded"
    admin = await ensure_admin(pipeline)
    before = (await admin.get("/admin/llm-configuration")).json()["current"]["id"]
    failed = await enable_ready_configuration(pipeline, model="test/invalid-structure")
    assert failed["status"] == "failed"
    after = (await admin.get("/admin/llm-configuration")).json()["current"]["id"]
    assert after == before


@pytest.mark.anyio
@pytest.mark.integration
async def test_cancel_stops_a_queued_probe(pipeline: Pipeline) -> None:
    _ = await enable_ready_configuration(pipeline)
    admin = await ensure_admin(pipeline)
    current_id = (await admin.get("/admin/llm-configuration")).json()["current"]["id"]
    created = await admin.post(
        "/admin/llm-configuration-attempts",
        json=candidate_attempt_payload(
            model="test/delayed-success",
            expected_current_version_id=current_id,
        ),
    )
    assert created.status_code == 202, created.text
    attempt_id = uuid.UUID(created.json()["id"])
    await divert_platform_outbox(pipeline, aggregate_id=attempt_id)
    cancelled = await admin.post(f"/admin/llm-configuration-attempts/{attempt_id}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    status = str(cancelled.json()["status"])
    if status == "cancel_requested":
        finished = await finish_attempt(pipeline, attempt_id)
        status = str(finished["status"])
    assert status == "cancelled"


@pytest.mark.anyio
@pytest.mark.integration
async def test_stale_expected_current_marks_the_attempt_conflicted(
    pipeline: Pipeline,
) -> None:
    first = await enable_ready_configuration(pipeline)
    assert first["status"] == "succeeded"
    admin = await ensure_admin(pipeline)
    current_id = (await admin.get("/admin/llm-configuration")).json()["current"]["id"]
    created = await admin.post(
        "/admin/llm-configuration-attempts",
        json=candidate_attempt_payload(
            model="test/success",
            expected_current_version_id=current_id,
        ),
    )
    assert created.status_code == 202, created.text
    attempt_id = uuid.UUID(created.json()["id"])
    await divert_platform_outbox(pipeline, aggregate_id=attempt_id)
    _ = await activate_current_model(pipeline, model="test/success")
    finished = await finish_attempt(pipeline, attempt_id)
    assert finished["status"] == "conflicted"


@pytest.mark.anyio
@pytest.mark.integration
async def test_search_interpretation_invalid_fails_without_replacing_current(
    pipeline: Pipeline,
) -> None:
    first = await enable_ready_configuration(pipeline)
    assert first["status"] == "succeeded"
    admin = await ensure_admin(pipeline)
    before = (await admin.get("/admin/llm-configuration")).json()["current"]
    failed = await enable_ready_configuration(
        pipeline,
        model="test/search-interpretation-invalid",
    )
    assert failed["status"] == "failed"
    after = (await admin.get("/admin/llm-configuration")).json()["current"]
    assert after["id"] == before["id"]
    calls = await admin.get("/admin/llm-calls?call_type=config_probe")
    assert calls.status_code == 200
    listed = calls.json()["calls"]
    assert any(item["model"] == "test/search-interpretation-invalid" for item in listed)


@pytest.mark.anyio
@pytest.mark.integration
async def test_copy_version_without_search_binding_probes_default_interpretation(
    pipeline: Pipeline,
) -> None:
    _ = await enable_ready_configuration(pipeline)
    admin = await ensure_admin(pipeline)
    workspace = (await admin.get("/admin/llm-configuration")).json()
    source = next(
        version
        for version in workspace["history"]
        if version["call_bindings"]["search_interpretation"] is None
    )
    created = await admin.post(
        f"/admin/llm-configurations/{source['id']}/copy-attempts",
        json={"expected_current_version_id": workspace["current"]["id"]},
    )
    assert created.status_code == 202, created.text
    snapshot = created.json()["candidate"]["call_bindings"]
    assert snapshot["search_interpretation"]["prompt_version_id"] == (
        manifest.SEARCH_INTERPRETATION_PROMPT_V1.id
    )
    assert snapshot["search_interpretation"]["request_timeout_seconds"] == 15
    attempt_id = uuid.UUID(created.json()["id"])
    await process_attempt(attempt_id, settings=pipeline.platform_settings())
    finished = await finish_attempt(pipeline, attempt_id)
    assert finished["status"] == "succeeded"
    current = (await admin.get("/admin/llm-configuration")).json()["current"]
    assert current["call_bindings"]["search_interpretation"]["prompt_version_id"] == (
        manifest.SEARCH_INTERPRETATION_PROMPT_V1.id
    )
