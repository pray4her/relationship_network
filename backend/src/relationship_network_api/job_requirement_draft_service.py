"""Editing lifecycle for validated job requirement draft snapshots."""

from __future__ import annotations

import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, cast, final

from sqlalchemy import select

from relationship_network_api import (
    job_requirement_schema_upgrade as schema_upgrade,
)
from relationship_network_api import tenant_audit_service, tenant_context
from relationship_network_api.job_requirement_validation import (
    INVALID_BUSINESS_RULE,
    INVALID_SCHEMA,
    RequirementResultValidationError,
    validate_editable_requirement_document,
)
from relationship_network_api.job_service import JobNotFoundError
from relationship_network_api.llm_assets import manifest
from relationship_network_api.models import (
    JOB_STATUS_ARCHIVED,
    Job,
    JobRequirementDraft,
    JobRequirementDraftSchemaUpgrade,
    JobRequirementParsingTask,
    JobRequirementSchemaVersion,
    LlmConfigurationCurrent,
    LlmConfigurationVersion,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]

DRAFT_NOT_FOUND: Final = "requirement_draft_not_found"
DRAFT_REVISION_CONFLICT: Final = "requirement_draft_revision_conflict"
DRAFT_LOCKED: Final = "requirement_draft_locked"
DRAFT_NOT_EDITABLE: Final = "requirement_draft_not_editable"
DRAFT_INVALID: Final = "requirement_draft_invalid"
JOB_ARCHIVED: Final = "job_archived"
SCHEMA_UPGRADE_UNAVAILABLE: Final = "requirement_schema_upgrade_unavailable"
SCHEMA_UPGRADE_NOT_FOUND: Final = "requirement_schema_upgrade_not_found"
SCHEMA_UPGRADE_RESOLUTION_INVALID: Final = "requirement_schema_upgrade_resolution_invalid"
SCHEMA_UPGRADE_LOSSY_UNRESOLVED: Final = "schema_upgrade_lossy_unresolved"

READ_ONLY_JOB_ARCHIVED: Final = "job_archived"
READ_ONLY_REPLACEMENT: Final = "replacement_in_progress"
READ_ONLY_STATUS: Final = "draft_not_editable"

ACTION_UPDATE: Final = "job_requirement_draft.update"
ACTION_ABANDON: Final = "job_requirement_draft.abandon"
ACTION_SCHEMA_UPGRADE: Final = "job_requirement_draft.schema_upgrade"
ACTION_RESOLVE_UPGRADE: Final = "job_requirement_draft.schema_upgrade_resolve"
TARGET_TYPE: Final = "job_requirement_draft"

RESOLUTION_DROP: Final = "drop"
RESOLUTION_DOWNGRADE: Final = "downgrade_unsupported"

NONTERMINAL_STATUSES: Final = ("queued", "running", "retry_scheduled", "cancel_requested")
NUMERIC_FIELDS: Final = {
    "qs_top200_rank",
    "world_top500_rank",
    "h_index",
    "total_citations",
}
BETWEEN_BOUND_COUNT: Final = 2


@final
class RequirementDraftError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        latest: RequirementDraftMutationView | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.latest = latest


@final
@dataclass(frozen=True)
class RequirementDraftMutationView:
    id: uuid.UUID
    task_id: uuid.UUID | None
    input_snapshot_id: uuid.UUID | None
    source_version_id: uuid.UUID | None
    requirement_schema_version_id: str
    status: str
    revision: int
    result: dict[str, object]
    updated_by: uuid.UUID | None
    status_changed_at: datetime
    read_only_reason: str | None
    field_catalog: dict[str, object]
    chinese_identity_values: list[str]
    created_at: datetime
    updated_at: datetime
    pending_upgrade_items: list[dict[str, object]] = field(default_factory=list)


@final
@dataclass(frozen=True)
class SchemaUpgradeRecordView:
    id: uuid.UUID
    draft_id: uuid.UUID
    from_schema_version_id: str
    to_schema_version_id: str
    converter_version: str
    item_mappings: list[dict[str, object]]
    lossy_resolutions: list[dict[str, object]]
    actor_user_id: uuid.UUID | None
    created_at: datetime


@final
@dataclass(frozen=True)
class SchemaUpgradeResultView:
    draft: RequirementDraftMutationView
    upgrade: SchemaUpgradeRecordView


@final
@dataclass(frozen=True)
class LossyResolutionSubmission:
    item_id: str
    resolution: str


def merge_editable_requirement_document(  # noqa: C901, PLR0912, PLR0915
    current: dict[str, object],
    submitted: dict[str, object],
    *,
    actor_user_id: uuid.UUID,
    changed_at: datetime,
) -> dict[str, object]:
    """Merge editable fields while preserving all server-owned provenance metadata."""
    timestamp = changed_at.isoformat()
    actor = str(actor_user_id)
    current_conditions: dict[str, tuple[str, dict[str, object]]] = {}
    for kind in ("hard_conditions", "preference_conditions"):
        for item in _object_list(current[kind]):
            current_conditions[cast("str", item["item_id"])] = (kind, item)
    used_ids: set[str] = set()

    def merge_condition(kind: str, raw: dict[str, object]) -> dict[str, object]:
        item_id_raw = raw.get("item_id")
        item_id = str(item_id_raw) if item_id_raw is not None else str(uuid.uuid4())
        if item_id in used_ids:
            raise RequirementResultValidationError(INVALID_BUSINESS_RULE, "duplicate item_id")
        used_ids.add(item_id)
        normalized = _normalize_condition(raw)
        existing_entry = current_conditions.get(item_id)
        if existing_entry is None:
            if item_id_raw is not None:
                raise RequirementResultValidationError(INVALID_BUSINESS_RULE, "unknown item_id")
            return {
                "item_id": item_id,
                "origin": "user_added",
                **normalized,
                "evidence": [],
                "model_snapshot": None,
                "last_modified_by": actor,
                "last_modified_at": timestamp,
            }
        previous_kind, existing = existing_entry
        changed = previous_kind != kind or any(
            existing[key] != normalized[key] for key in normalized
        )
        return {
            "item_id": item_id,
            "origin": existing["origin"],
            **normalized,
            "evidence": deepcopy(existing["evidence"]),
            "model_snapshot": deepcopy(existing["model_snapshot"]),
            "last_modified_by": actor if changed else existing["last_modified_by"],
            "last_modified_at": timestamp if changed else existing["last_modified_at"],
        }

    merged_hard = [
        merge_condition("hard_conditions", item)
        for item in _object_list(submitted["hard_conditions"])
    ]
    merged_preferences = [
        merge_condition("preference_conditions", item)
        for item in _object_list(submitted["preference_conditions"])
    ]

    current_unsupported = {
        cast("str", item["item_id"]): item
        for item in _object_list(current["unsupported_conditions"])
    }

    def merge_unsupported(raw: dict[str, object]) -> dict[str, object]:
        item_id_raw = raw.get("item_id")
        item_id = str(item_id_raw) if item_id_raw is not None else str(uuid.uuid4())
        if item_id in used_ids:
            raise RequirementResultValidationError(INVALID_BUSINESS_RULE, "duplicate item_id")
        used_ids.add(item_id)
        description = _trimmed_text(raw.get("description"), "unsupported description")
        existing = current_unsupported.get(item_id)
        if existing is None:
            if item_id_raw is not None:
                raise RequirementResultValidationError(INVALID_BUSINESS_RULE, "unknown item_id")
            return {
                "item_id": item_id,
                "origin": "user_added",
                "description": description,
                "evidence": [],
                "model_snapshot": None,
                "last_modified_by": actor,
                "last_modified_at": timestamp,
            }
        changed = existing["description"] != description
        return {
            "item_id": item_id,
            "origin": existing["origin"],
            "description": description,
            "evidence": deepcopy(existing["evidence"]),
            "model_snapshot": deepcopy(existing["model_snapshot"]),
            "last_modified_by": actor if changed else existing["last_modified_by"],
            "last_modified_at": timestamp if changed else existing["last_modified_at"],
        }

    merged_unsupported = [
        merge_unsupported(item) for item in _object_list(submitted["unsupported_conditions"])
    ]
    removed = deepcopy(_object_list(current["removed_facts"]))
    for item_id, (kind, item) in current_conditions.items():
        if item_id not in used_ids:
            removed.append(
                _removed_fact(
                    item,
                    kind="hard_condition" if kind == "hard_conditions" else "preference_condition",
                    actor=actor,
                    timestamp=timestamp,
                )
            )
    for item_id, item in current_unsupported.items():
        if item_id not in used_ids:
            removed.append(
                _removed_fact(
                    item,
                    kind="unsupported_condition",
                    actor=actor,
                    timestamp=timestamp,
                )
            )

    submitted_query = _trimmed_text(submitted.get("research_topic_query"), "research topic query")
    current_query = cast("dict[str, object]", current["research_topic_query"])
    query_changed = current_query["value"] != submitted_query
    merged_query = {
        "value": submitted_query,
        "model_value": current_query["model_value"],
        "last_modified_by": actor if query_changed else current_query["last_modified_by"],
        "last_modified_at": timestamp if query_changed else current_query["last_modified_at"],
    }

    current_conflicts = {
        cast("str", item["item_id"]): item for item in _object_list(current["source_conflicts"])
    }
    submitted_conflicts = _object_list(submitted["source_conflicts"])
    if len(submitted_conflicts) != len(current_conflicts):
        raise RequirementResultValidationError(
            INVALID_BUSINESS_RULE,
            "all source conflicts must be submitted",
        )
    merged_conflicts: list[dict[str, object]] = []
    conflict_ids: set[str] = set()
    for raw in submitted_conflicts:
        item_id_raw = raw.get("item_id")
        item_id = str(item_id_raw) if item_id_raw is not None else ""
        if item_id in conflict_ids or item_id not in current_conflicts:
            raise RequirementResultValidationError(
                INVALID_BUSINESS_RULE,
                "invalid source conflict item_id",
            )
        conflict_ids.add(item_id)
        existing = current_conflicts[item_id]
        note_raw = raw.get("resolution_note")
        if note_raw is None:
            resolution = None
        else:
            note = _trimmed_text(note_raw, "source conflict resolution note")
            previous = existing["resolution"]
            if isinstance(previous, dict) and previous.get("note") == note:
                resolution = deepcopy(cast("dict[str, object]", previous))
            else:
                resolution = {"note": note, "resolved_by": actor, "resolved_at": timestamp}
        merged_conflicts.append(
            {
                "item_id": item_id,
                "description": existing["description"],
                "evidence": deepcopy(existing["evidence"]),
                "model_snapshot": deepcopy(existing["model_snapshot"]),
                "resolution": resolution,
            }
        )
    return {
        "hard_conditions": merged_hard,
        "preference_conditions": merged_preferences,
        "research_topic_query": merged_query,
        "unsupported_conditions": merged_unsupported,
        "source_conflicts": merged_conflicts,
        "removed_facts": removed,
    }


async def update_requirement_draft(  # noqa: PLR0913
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    draft_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    expected_revision: int,
    submitted: dict[str, object],
) -> RequirementDraftMutationView:
    job = await _load_job(session, tenant_id=tenant_id, job_id=job_id)
    draft = await _locked_draft(
        session,
        tenant_id=tenant_id,
        job_id=job_id,
        draft_id=draft_id,
    )
    if draft is None:
        raise RequirementDraftError(DRAFT_NOT_FOUND)
    schema = await _schema(session, draft.requirement_schema_version_id)
    await _assert_mutable(
        session,
        job=job,
        draft=draft,
        schema=schema,
        expected_revision=expected_revision,
        actor_user_id=actor_user_id,
        action=ACTION_UPDATE,
    )
    changed_at = datetime.now(UTC)
    try:
        merged = merge_editable_requirement_document(
            draft.result_json,
            submitted,
            actor_user_id=actor_user_id,
            changed_at=changed_at,
        )
        validated = validate_editable_requirement_document(
            merged,
            schema=manifest.read_requirement_editor_schema(draft.requirement_schema_version_id),
            asset=_asset(draft.requirement_schema_version_id),
        )
    except RequirementResultValidationError as error:
        await _reject(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            draft_id=draft_id,
            action=ACTION_UPDATE,
            code=DRAFT_INVALID,
        )
        message = "unreachable"
        raise AssertionError(message) from error
    draft.result_json = validated
    draft.revision += 1
    draft.updated_by = actor_user_id
    tenant_audit_service.record_event(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=ACTION_UPDATE,
        target_type=TARGET_TYPE,
        target_id=str(draft.id),
        result=tenant_audit_service.AUDIT_RESULT_SUCCESS,
        detail=f"revision={draft.revision}",
    )
    # updated_at is server-owned (onupdate); reload it before the commit.
    await session.flush()
    await session.refresh(draft)
    await session.commit()
    pending = await pending_schema_upgrade_items(
        session,
        tenant_id=tenant_id,
        draft_id=draft.id,
    )
    return _view(draft, schema=schema, read_only_reason=None, pending_upgrade_items=pending)


async def abandon_requirement_draft(  # noqa: PLR0913
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    draft_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    expected_revision: int,
) -> RequirementDraftMutationView:
    job = await _load_job(session, tenant_id=tenant_id, job_id=job_id)
    draft = await _locked_draft(
        session,
        tenant_id=tenant_id,
        job_id=job_id,
        draft_id=draft_id,
    )
    if draft is None:
        raise RequirementDraftError(DRAFT_NOT_FOUND)
    schema = await _schema(session, draft.requirement_schema_version_id)
    await _assert_mutable(
        session,
        job=job,
        draft=draft,
        schema=schema,
        expected_revision=expected_revision,
        actor_user_id=actor_user_id,
        action=ACTION_ABANDON,
    )
    draft.status = "abandoned"
    draft.revision += 1
    draft.updated_by = actor_user_id
    draft.status_changed_at = datetime.now(UTC)
    tenant_audit_service.record_event(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=ACTION_ABANDON,
        target_type=TARGET_TYPE,
        target_id=str(draft.id),
        result=tenant_audit_service.AUDIT_RESULT_SUCCESS,
        detail=f"revision={draft.revision}",
    )
    # updated_at is server-owned (onupdate); reload it before the commit.
    await session.flush()
    await session.refresh(draft)
    await session.commit()
    pending = await pending_schema_upgrade_items(
        session,
        tenant_id=tenant_id,
        draft_id=draft.id,
    )
    return _view(
        draft,
        schema=schema,
        read_only_reason=READ_ONLY_STATUS,
        pending_upgrade_items=pending,
    )


async def pending_schema_upgrade_items(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    draft_id: uuid.UUID,
) -> list[dict[str, object]]:
    """Return the unresolved pending upgrade items recorded for a draft."""
    upgrades = (
        (
            await session.execute(
                select(JobRequirementDraftSchemaUpgrade)
                .where(
                    JobRequirementDraftSchemaUpgrade.tenant_id == tenant_id,
                    JobRequirementDraftSchemaUpgrade.draft_id == draft_id,
                )
                .order_by(JobRequirementDraftSchemaUpgrade.created_at)
            )
        )
        .scalars()
        .all()
    )
    pending: list[dict[str, object]] = []
    for upgrade in upgrades:
        pending.extend(
            {
                "item_id": entry["item_id"],
                "kind": entry["kind"],
                "snapshot": deepcopy(cast("dict[str, object]", entry["snapshot"])),
            }
            for entry in upgrade.lossy_resolutions
            if entry["resolution"] is None
        )
    return pending


async def upgrade_draft_schema(  # noqa: PLR0913
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    draft_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    expected_revision: int,
) -> SchemaUpgradeResultView:
    """Explicitly upgrade an editable draft to the current configuration's schema.

    The target schema is derived from the prompt bound to the current LLM
    configuration, and only the registered deterministic converter runs —
    never an LLM re-interpretation of historical content.
    """
    job = await _load_job(session, tenant_id=tenant_id, job_id=job_id)
    draft = await _locked_draft(
        session,
        tenant_id=tenant_id,
        job_id=job_id,
        draft_id=draft_id,
    )
    if draft is None:
        raise RequirementDraftError(DRAFT_NOT_FOUND)
    schema = await _schema(session, draft.requirement_schema_version_id)
    await _assert_mutable(
        session,
        job=job,
        draft=draft,
        schema=schema,
        expected_revision=expected_revision,
        actor_user_id=actor_user_id,
        action=ACTION_SCHEMA_UPGRADE,
    )
    target_schema_id = await _current_prompt_compatible_schema_id(session)
    converter = (
        None
        if target_schema_id is None
        else schema_upgrade.converter_version_for(
            draft.requirement_schema_version_id,
            target_schema_id,
        )
    )
    if (
        target_schema_id is None
        or target_schema_id == draft.requirement_schema_version_id
        or converter is None
    ):
        await _reject(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            draft_id=draft.id,
            action=ACTION_SCHEMA_UPGRADE,
            code=SCHEMA_UPGRADE_UNAVAILABLE,
        )
    conversion = schema_upgrade.convert_document(
        draft.result_json,
        from_schema_id=draft.requirement_schema_version_id,
        to_schema_id=cast("str", target_schema_id),
    )
    try:
        validated = validate_editable_requirement_document(
            conversion.document,
            schema=manifest.read_requirement_editor_schema(cast("str", target_schema_id)),
            asset=_asset(cast("str", target_schema_id)),
        )
    except RequirementResultValidationError as error:
        await _reject(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            draft_id=draft.id,
            action=ACTION_SCHEMA_UPGRADE,
            code=DRAFT_INVALID,
        )
        message = "unreachable"
        raise AssertionError(message) from error
    upgrade = JobRequirementDraftSchemaUpgrade(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        job_id=job_id,
        draft_id=draft.id,
        from_schema_version_id=draft.requirement_schema_version_id,
        to_schema_version_id=cast("str", target_schema_id),
        converter_version=cast("str", converter),
        pre_upgrade_json=deepcopy(draft.result_json),
        item_mappings=conversion.item_mappings,
        lossy_resolutions=[
            {
                "item_id": item["item_id"],
                "kind": item["kind"],
                "snapshot": item["snapshot"],
                "resolution": None,
            }
            for item in conversion.lossy_items
        ],
        actor_user_id=actor_user_id,
    )
    session.add(upgrade)
    draft.result_json = validated
    draft.requirement_schema_version_id = cast("str", target_schema_id)
    draft.revision += 1
    draft.updated_by = actor_user_id
    tenant_audit_service.record_event(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=ACTION_SCHEMA_UPGRADE,
        target_type=TARGET_TYPE,
        target_id=str(draft.id),
        result=tenant_audit_service.AUDIT_RESULT_SUCCESS,
        detail=(
            f"from={upgrade.from_schema_version_id} to={upgrade.to_schema_version_id} "
            f"converter={upgrade.converter_version} lossy={len(conversion.lossy_items)} "
            f"revision={draft.revision}"
        ),
    )
    # updated_at is server-owned (onupdate); reload it before the commit.
    await session.flush()
    await session.refresh(draft)
    await session.commit()
    target_schema = await _schema(session, cast("str", target_schema_id))
    pending = [
        {"item_id": item["item_id"], "kind": item["kind"], "snapshot": deepcopy(item["snapshot"])}
        for item in conversion.lossy_items
    ]
    return SchemaUpgradeResultView(
        draft=_view(
            draft,
            schema=target_schema,
            read_only_reason=None,
            pending_upgrade_items=pending,
        ),
        upgrade=_upgrade_view(upgrade),
    )


async def resolve_schema_upgrade_lossy_items(  # noqa: PLR0913
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    draft_id: uuid.UUID,
    upgrade_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    expected_revision: int,
    resolutions: list[LossyResolutionSubmission],
) -> RequirementDraftMutationView:
    """Apply member-chosen deterministic resolutions to pending upgrade items."""
    job = await _load_job(session, tenant_id=tenant_id, job_id=job_id)
    draft = await _locked_draft(
        session,
        tenant_id=tenant_id,
        job_id=job_id,
        draft_id=draft_id,
    )
    if draft is None:
        raise RequirementDraftError(DRAFT_NOT_FOUND)
    schema = await _schema(session, draft.requirement_schema_version_id)
    await _assert_mutable(
        session,
        job=job,
        draft=draft,
        schema=schema,
        expected_revision=expected_revision,
        actor_user_id=actor_user_id,
        action=ACTION_RESOLVE_UPGRADE,
    )
    upgrade = (
        await session.execute(
            select(JobRequirementDraftSchemaUpgrade)
            .where(
                JobRequirementDraftSchemaUpgrade.id == upgrade_id,
                JobRequirementDraftSchemaUpgrade.tenant_id == tenant_id,
                JobRequirementDraftSchemaUpgrade.job_id == job_id,
                JobRequirementDraftSchemaUpgrade.draft_id == draft_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if upgrade is None:
        raise RequirementDraftError(SCHEMA_UPGRADE_NOT_FOUND)
    entries = deepcopy(upgrade.lossy_resolutions)
    by_item_id = {cast("str", entry["item_id"]): entry for entry in entries}
    changed_at = datetime.now(UTC)
    actor = str(actor_user_id)
    timestamp = changed_at.isoformat()
    document = deepcopy(draft.result_json)
    for submission in resolutions:
        entry = by_item_id.get(submission.item_id)
        if (
            entry is None
            or entry["resolution"] is not None
            or submission.resolution not in {RESOLUTION_DROP, RESOLUTION_DOWNGRADE}
        ):
            await _reject(
                session,
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                draft_id=draft.id,
                action=ACTION_RESOLVE_UPGRADE,
                code=SCHEMA_UPGRADE_RESOLUTION_INVALID,
            )
            message = "unreachable"
            raise AssertionError(message)
        snapshot = cast("dict[str, object]", entry["snapshot"])
        if submission.resolution == RESOLUTION_DROP:
            cast("list[object]", document["removed_facts"]).append(
                _removed_fact(
                    snapshot,
                    kind=cast("str", entry["kind"]),
                    actor=actor,
                    timestamp=timestamp,
                )
            )
        else:
            cast("list[object]", document["unsupported_conditions"]).append(
                {
                    "item_id": str(uuid.uuid4()),
                    "origin": "user_added",
                    "description": cast("str", snapshot["description"]),
                    "evidence": [],
                    "model_snapshot": None,
                    "last_modified_by": actor,
                    "last_modified_at": timestamp,
                }
            )
        entry["resolution"] = {
            "choice": submission.resolution,
            "resolved_by": actor,
            "resolved_at": timestamp,
        }
    try:
        validated = validate_editable_requirement_document(
            document,
            schema=manifest.read_requirement_editor_schema(draft.requirement_schema_version_id),
            asset=_asset(draft.requirement_schema_version_id),
        )
    except RequirementResultValidationError as error:
        await _reject(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            draft_id=draft.id,
            action=ACTION_RESOLVE_UPGRADE,
            code=DRAFT_INVALID,
        )
        message = "unreachable"
        raise AssertionError(message) from error
    draft.result_json = validated
    draft.revision += 1
    draft.updated_by = actor_user_id
    upgrade.lossy_resolutions = entries
    tenant_audit_service.record_event(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=ACTION_RESOLVE_UPGRADE,
        target_type=TARGET_TYPE,
        target_id=str(draft.id),
        result=tenant_audit_service.AUDIT_RESULT_SUCCESS,
        detail=f"resolved={len(resolutions)} revision={draft.revision}",
    )
    # updated_at is server-owned (onupdate); reload it before the commit.
    await session.flush()
    await session.refresh(draft)
    await session.commit()
    pending = await pending_schema_upgrade_items(
        session,
        tenant_id=tenant_id,
        draft_id=draft.id,
    )
    return _view(draft, schema=schema, read_only_reason=None, pending_upgrade_items=pending)


async def _current_prompt_compatible_schema_id(session: AsyncSession) -> str | None:
    configuration = (
        await session.execute(
            select(LlmConfigurationVersion)
            .join(
                LlmConfigurationCurrent,
                LlmConfigurationCurrent.version_id == LlmConfigurationVersion.id,
            )
            .where(LlmConfigurationCurrent.singleton)
        )
    ).scalar_one_or_none()
    if configuration is None:
        return None
    try:
        return manifest.prompt_asset(configuration.prompt_version_id).compatible_schema_version_id
    except manifest.LlmAssetError:
        return None


def _upgrade_view(upgrade: JobRequirementDraftSchemaUpgrade) -> SchemaUpgradeRecordView:
    return SchemaUpgradeRecordView(
        id=upgrade.id,
        draft_id=upgrade.draft_id,
        from_schema_version_id=upgrade.from_schema_version_id,
        to_schema_version_id=upgrade.to_schema_version_id,
        converter_version=upgrade.converter_version,
        item_mappings=deepcopy(upgrade.item_mappings),
        lossy_resolutions=deepcopy(upgrade.lossy_resolutions),
        actor_user_id=upgrade.actor_user_id,
        created_at=upgrade.created_at,
    )


async def read_only_reason(
    session: AsyncSession,
    *,
    job: Job,
    draft: JobRequirementDraft,
) -> str | None:
    if job.status == JOB_STATUS_ARCHIVED:
        return READ_ONLY_JOB_ARCHIVED
    if draft.status != "editable":
        return READ_ONLY_STATUS
    replacement = (
        await session.execute(
            select(JobRequirementParsingTask.id).where(
                JobRequirementParsingTask.tenant_id == draft.tenant_id,
                JobRequirementParsingTask.job_id == draft.job_id,
                JobRequirementParsingTask.replaces_draft_id == draft.id,
                JobRequirementParsingTask.status.in_(NONTERMINAL_STATUSES),
            )
        )
    ).scalar_one_or_none()
    return READ_ONLY_REPLACEMENT if replacement is not None else None


def draft_view(
    draft: JobRequirementDraft,
    *,
    schema: JobRequirementSchemaVersion,
    reason: str | None,
) -> RequirementDraftMutationView:
    return _view(draft, schema=schema, read_only_reason=reason)


async def _assert_mutable(  # noqa: PLR0913
    session: AsyncSession,
    *,
    job: Job,
    draft: JobRequirementDraft,
    schema: JobRequirementSchemaVersion,
    expected_revision: int,
    actor_user_id: uuid.UUID,
    action: str,
) -> None:
    reason = await read_only_reason(session, job=job, draft=draft)
    if reason == READ_ONLY_JOB_ARCHIVED:
        await _reject(
            session,
            tenant_id=draft.tenant_id,
            actor_user_id=actor_user_id,
            draft_id=draft.id,
            action=action,
            code=JOB_ARCHIVED,
        )
    if reason == READ_ONLY_REPLACEMENT:
        await _reject(
            session,
            tenant_id=draft.tenant_id,
            actor_user_id=actor_user_id,
            draft_id=draft.id,
            action=action,
            code=DRAFT_LOCKED,
        )
    if reason == READ_ONLY_STATUS:
        await _reject(
            session,
            tenant_id=draft.tenant_id,
            actor_user_id=actor_user_id,
            draft_id=draft.id,
            action=action,
            code=DRAFT_NOT_EDITABLE,
        )
    if draft.revision != expected_revision:
        latest = _view(draft, schema=schema, read_only_reason=reason)
        await _reject(
            session,
            tenant_id=draft.tenant_id,
            actor_user_id=actor_user_id,
            draft_id=draft.id,
            action=action,
            code=DRAFT_REVISION_CONFLICT,
            latest=latest,
        )


async def _reject(  # noqa: PLR0913
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    draft_id: uuid.UUID,
    action: str,
    code: str,
    latest: RequirementDraftMutationView | None = None,
) -> None:
    await session.rollback()
    await tenant_context.set_tenant_context(session, tenant_id)
    tenant_audit_service.record_event(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=action,
        target_type=TARGET_TYPE,
        target_id=str(draft_id),
        result=tenant_audit_service.AUDIT_RESULT_FAILURE,
        detail=code,
    )
    await session.commit()
    raise RequirementDraftError(code, latest=latest)


async def _load_job(session: AsyncSession, *, tenant_id: uuid.UUID, job_id: uuid.UUID) -> Job:
    job = (
        await session.execute(
            select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id).with_for_update()
        )
    ).scalar_one_or_none()
    if job is None:
        raise JobNotFoundError
    return job


async def _locked_draft(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    draft_id: uuid.UUID,
) -> JobRequirementDraft | None:
    return (
        await session.execute(
            select(JobRequirementDraft)
            .where(
                JobRequirementDraft.id == draft_id,
                JobRequirementDraft.tenant_id == tenant_id,
                JobRequirementDraft.job_id == job_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()


async def _schema(session: AsyncSession, schema_id: str) -> JobRequirementSchemaVersion:
    return (
        await session.execute(
            select(JobRequirementSchemaVersion).where(JobRequirementSchemaVersion.id == schema_id)
        )
    ).scalar_one()


def _asset(schema_id: str) -> manifest.RequirementSchemaAsset:
    asset = next(
        (item for item in manifest.REQUIREMENT_SCHEMA_ASSETS if item.id == schema_id), None
    )
    if asset is None or asset.editor_path is None:
        raise RequirementResultValidationError(INVALID_SCHEMA, "editor Schema is unavailable")
    return asset


def _view(
    draft: JobRequirementDraft,
    *,
    schema: JobRequirementSchemaVersion,
    read_only_reason: str | None,
    pending_upgrade_items: list[dict[str, object]] | None = None,
) -> RequirementDraftMutationView:
    return RequirementDraftMutationView(
        id=draft.id,
        task_id=draft.task_id,
        input_snapshot_id=draft.input_snapshot_id,
        source_version_id=draft.source_version_id,
        requirement_schema_version_id=draft.requirement_schema_version_id,
        status=draft.status,
        revision=draft.revision,
        result=deepcopy(draft.result_json),
        updated_by=draft.updated_by,
        status_changed_at=draft.status_changed_at,
        read_only_reason=read_only_reason,
        field_catalog=deepcopy(schema.field_catalog),
        chinese_identity_values=list(schema.chinese_identity_values),
        created_at=draft.created_at,
        updated_at=draft.updated_at,
        pending_upgrade_items=deepcopy(pending_upgrade_items or []),
    )


def _removed_fact(
    item: dict[str, object],
    *,
    kind: str,
    actor: str,
    timestamp: str,
) -> dict[str, object]:
    return {
        "item_id": item["item_id"],
        "kind": kind,
        "origin": item["origin"],
        "model_snapshot": deepcopy(item["model_snapshot"]),
        "removed_snapshot": deepcopy(item),
        "removed_by": actor,
        "removed_at": timestamp,
    }


def _normalize_condition(raw: dict[str, object]) -> dict[str, object]:  # noqa: PLR0912
    field = cast("str", raw.get("field"))
    operator = cast("str", raw.get("operator"))
    description = _trimmed_text(raw.get("description"), "condition description")
    value = raw.get("value")
    if field in NUMERIC_FIELDS:
        if operator == "between":
            if not isinstance(value, list):
                raise RequirementResultValidationError(
                    INVALID_BUSINESS_RULE, "between requires two numeric bounds"
                )
            values = cast("list[object]", value)
            if len(values) != BETWEEN_BOUND_COUNT:
                raise RequirementResultValidationError(
                    INVALID_BUSINESS_RULE, "between requires two numeric bounds"
                )
            bounds = [_number(item) for item in values]
            normalized_value: object = bounds
        else:
            normalized_value = _number(value)
    elif field == "chinese_identity":
        if operator == "eq":
            normalized_value = _trimmed_text(value, "chinese identity")
        else:
            normalized_value = _string_list(value, "chinese identity")
    elif field == "country":
        if operator == "eq":
            normalized_value = _trimmed_text(value, "country")
        else:
            normalized_value = _string_list(value, "country")
    elif field == "current_affiliation":
        normalized_value = _trimmed_text(value, "current affiliation")
    else:
        normalized_value = value
    return {
        "field": field,
        "operator": operator,
        "value": normalized_value,
        "description": description,
    }


def _trimmed_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RequirementResultValidationError(
            INVALID_BUSINESS_RULE,
            f"{label} must be non-empty",
        )
    return value.strip()


def _number(value: object) -> int | float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise RequirementResultValidationError(INVALID_BUSINESS_RULE, "numeric value required")
    return value


def _string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise RequirementResultValidationError(INVALID_BUSINESS_RULE, f"{label} list required")
    normalized: list[str] = []
    for item in cast("list[object]", value):
        text = _trimmed_text(item, label)
        if text not in normalized:
            normalized.append(text)
    if not normalized:
        raise RequirementResultValidationError(INVALID_BUSINESS_RULE, f"{label} list required")
    return normalized


def _object_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise RequirementResultValidationError(INVALID_SCHEMA, "object list required")
    return [cast("dict[str, object]", item) for item in value]
