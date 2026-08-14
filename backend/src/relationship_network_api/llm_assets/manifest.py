from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib import resources
from typing import Final, Literal, cast

LlmPromptCallType = Literal["job_requirement_parsing", "search_interpretation"]
CALL_TYPE_JOB_REQUIREMENT_PARSING: Final = "job_requirement_parsing"
CALL_TYPE_SEARCH_INTERPRETATION: Final = "search_interpretation"
DECLARED_CALL_TYPES: Final[tuple[LlmPromptCallType, ...]] = (
    CALL_TYPE_JOB_REQUIREMENT_PARSING,
    CALL_TYPE_SEARCH_INTERPRETATION,
)


class LlmAssetError(ValueError):
    """Raised when a deployed immutable LLM asset is missing or has drifted."""


@dataclass(frozen=True)
class RequirementSchemaAsset:
    id: str
    package: str
    path: str
    sha256: str
    schema_id: str
    field_catalog: dict[str, tuple[str, ...]]
    chinese_identity_values: tuple[str, ...]
    output_limits: dict[str, int]
    editor_package: str | None = None
    editor_path: str | None = None
    editor_sha256: str | None = None
    editor_schema_id: str | None = None


@dataclass(frozen=True)
class SearchInterpretationSchemaAsset:
    id: str
    package: str
    path: str
    sha256: str
    schema_id: str
    compatible_schema_version_id: str


@dataclass(frozen=True)
class PromptAsset:
    id: str
    package: str
    path: str
    sha256: str
    compatible_schema_version_id: str
    call_type: LlmPromptCallType
    output_schema_version_id: str | None = None


JOB_REQUIREMENT_SCHEMA_V1: Final = RequirementSchemaAsset(
    id="job-requirement-schema-v1",
    package="relationship_network_api.llm_assets.job_requirement",
    path="schema_v1.json",
    sha256="1b1eaa1cbb5a196b381158b140c1f87d3b22251eee278b920fe3fed25c7ad49e",
    schema_id="urn:relationship-network:job-requirement-schema:v1",
    field_catalog={
        "qs_top200_rank": ("gte", "lte", "between"),
        "world_top500_rank": ("gte", "lte", "between"),
        "h_index": ("gte", "lte", "between"),
        "total_citations": ("gte", "lte", "between"),
        "chinese_identity": ("eq", "in"),
        "country": ("eq", "in"),
        "current_affiliation": ("match", "match_phrase"),
    },
    chinese_identity_values=("国内华人", "海外华人", "外国人"),
    output_limits={
        "combined_conditions": 100,
        "source_conflicts": 50,
        "research_topic_query_characters": 4000,
        "description_characters": 2000,
        "evidence_quote_characters": 2000,
    },
)

JOB_REQUIREMENT_PROMPT_V1: Final = PromptAsset(
    id="job-requirement-prompt-v1",
    package="relationship_network_api.llm_assets.job_requirement",
    path="prompt_v1.txt",
    sha256="aa0166f8fe7cedf52aa7a6b2e0b4e0002905aad5fde7011b532ef14dd69c8372",
    compatible_schema_version_id=JOB_REQUIREMENT_SCHEMA_V1.id,
    call_type=CALL_TYPE_JOB_REQUIREMENT_PARSING,
)

JOB_REQUIREMENT_SCHEMA_V2: Final = RequirementSchemaAsset(
    id="job-requirement-schema-v2",
    package="relationship_network_api.llm_assets.job_requirement",
    path="schema_v2.json",
    sha256="66c29d52731513a2a6a398774af5ac9ca9c461b868b99f9a66b70a59cf6b946c",
    schema_id="urn:relationship-network:job-requirement-schema:v2",
    field_catalog=JOB_REQUIREMENT_SCHEMA_V1.field_catalog,
    chinese_identity_values=JOB_REQUIREMENT_SCHEMA_V1.chinese_identity_values,
    output_limits=JOB_REQUIREMENT_SCHEMA_V1.output_limits,
    editor_package="relationship_network_api.llm_assets.job_requirement",
    editor_path="editor_schema_v2.json",
    editor_sha256="3ffebbb8ac7336612a1eccb2dd70ee7b1bafe3efedc123759dee4fb2fd6a32ec",
    editor_schema_id="urn:relationship-network:job-requirement-editor-schema:v2",
)

JOB_REQUIREMENT_PROMPT_V2: Final = PromptAsset(
    id="job-requirement-prompt-v2",
    package="relationship_network_api.llm_assets.job_requirement",
    path="prompt_v2.txt",
    sha256="b7170479abdc088eccbeec73798a3e6ac7e1c637a37cefaa7c74d3ec498d6101",
    compatible_schema_version_id=JOB_REQUIREMENT_SCHEMA_V2.id,
    call_type=CALL_TYPE_JOB_REQUIREMENT_PARSING,
)

SEARCH_INTERPRETATION_SCHEMA_V1: Final = SearchInterpretationSchemaAsset(
    id="search-interpretation-schema-v1",
    package="relationship_network_api.llm_assets.search_interpretation",
    path="schema_v1.json",
    sha256="606cf84667c57237c83f0d963028d72b18f69ac24d3d8592b3a12090228587d0",
    schema_id="urn:relationship-network:search-interpretation-schema:v1",
    compatible_schema_version_id=JOB_REQUIREMENT_SCHEMA_V1.id,
)

SEARCH_INTERPRETATION_PROMPT_V1: Final = PromptAsset(
    id="search-interpretation-prompt-v1",
    package="relationship_network_api.llm_assets.search_interpretation",
    path="prompt_v1.txt",
    sha256="ed01b8c19f4565d133c8d6bced7f8660c723a2266f67109db423de21f849392f",
    compatible_schema_version_id=JOB_REQUIREMENT_SCHEMA_V1.id,
    call_type=CALL_TYPE_SEARCH_INTERPRETATION,
    output_schema_version_id=SEARCH_INTERPRETATION_SCHEMA_V1.id,
)

REQUIREMENT_SCHEMA_ASSETS: Final = (JOB_REQUIREMENT_SCHEMA_V1, JOB_REQUIREMENT_SCHEMA_V2)
SEARCH_INTERPRETATION_SCHEMA_ASSETS: Final = (SEARCH_INTERPRETATION_SCHEMA_V1,)
PROMPT_ASSETS: Final = (
    JOB_REQUIREMENT_PROMPT_V1,
    JOB_REQUIREMENT_PROMPT_V2,
    SEARCH_INTERPRETATION_PROMPT_V1,
)
SEARCH_INTERPRETATION_JSON_SCHEMA_NAME: Final = "relationship_network_search_interpretation"
JOB_REQUIREMENT_JSON_SCHEMA_NAME: Final = "relationship_network_job_requirement"


def _read_asset(package: str, path: str) -> bytes:
    try:
        return resources.files(package).joinpath(path).read_bytes()
    except (FileNotFoundError, ModuleNotFoundError) as error:
        message = f"missing LLM asset: {package}/{path}"
        raise LlmAssetError(message) from error


def _verify_hash(content: bytes, *, asset_id: str, expected_sha256: str) -> None:
    actual = hashlib.sha256(content).hexdigest()
    if actual != expected_sha256:
        message = (
            f"LLM asset hash mismatch for {asset_id}: expected {expected_sha256}, got {actual}"
        )
        raise LlmAssetError(message)


def validate_deployed_assets() -> None:
    """Reject duplicate IDs, missing assets, incompatible declarations, and hash drift."""
    schema_ids = [asset.id for asset in REQUIREMENT_SCHEMA_ASSETS]
    search_schema_ids = [asset.id for asset in SEARCH_INTERPRETATION_SCHEMA_ASSETS]
    prompt_ids = [asset.id for asset in PROMPT_ASSETS]
    if (
        len(schema_ids) != len(set(schema_ids))
        or len(search_schema_ids) != len(set(search_schema_ids))
        or len(prompt_ids) != len(set(prompt_ids))
        or set(schema_ids) & set(search_schema_ids)
    ):
        message = "duplicate deployed LLM asset ID"
        raise LlmAssetError(message)
    known_schema_ids = set(schema_ids)
    known_search_schema_ids = set(search_schema_ids)
    for asset in REQUIREMENT_SCHEMA_ASSETS:
        _validate_requirement_schema_asset(asset)
    for asset in SEARCH_INTERPRETATION_SCHEMA_ASSETS:
        _validate_search_interpretation_schema_asset(
            asset,
            known_schema_ids=known_schema_ids,
        )
    for asset in PROMPT_ASSETS:
        _validate_prompt_asset(
            asset,
            known_schema_ids=known_schema_ids,
            known_search_schema_ids=known_search_schema_ids,
        )


def _validate_requirement_schema_asset(asset: RequirementSchemaAsset) -> None:
    content = _read_asset(asset.package, asset.path)
    _verify_hash(content, asset_id=asset.id, expected_sha256=asset.sha256)
    schema = cast("dict[str, object]", json.loads(content))
    if schema.get("$id") != asset.schema_id:
        message = f"Schema ID mismatch for {asset.id}"
        raise LlmAssetError(message)
    editor_declaration = (
        asset.editor_package,
        asset.editor_path,
        asset.editor_sha256,
        asset.editor_schema_id,
    )
    if any(part is not None for part in editor_declaration):
        if any(part is None for part in editor_declaration):
            message = f"incomplete editor Schema declaration for {asset.id}"
            raise LlmAssetError(message)
        editor_content = _read_asset(
            cast("str", asset.editor_package),
            cast("str", asset.editor_path),
        )
        _verify_hash(
            editor_content,
            asset_id=f"{asset.id}:editor",
            expected_sha256=cast("str", asset.editor_sha256),
        )
        editor_schema = cast("dict[str, object]", json.loads(editor_content))
        if editor_schema.get("$id") != asset.editor_schema_id:
            message = f"editor Schema ID mismatch for {asset.id}"
            raise LlmAssetError(message)


def _validate_search_interpretation_schema_asset(
    asset: SearchInterpretationSchemaAsset,
    *,
    known_schema_ids: set[str],
) -> None:
    if asset.compatible_schema_version_id not in known_schema_ids:
        message = f"unknown compatible Schema for {asset.id}"
        raise LlmAssetError(message)
    content = _read_asset(asset.package, asset.path)
    _verify_hash(content, asset_id=asset.id, expected_sha256=asset.sha256)
    schema = cast("dict[str, object]", json.loads(content))
    if schema.get("$id") != asset.schema_id:
        message = f"Schema ID mismatch for {asset.id}"
        raise LlmAssetError(message)


def _validate_prompt_asset(
    asset: PromptAsset,
    *,
    known_schema_ids: set[str],
    known_search_schema_ids: set[str],
) -> None:
    if asset.compatible_schema_version_id not in known_schema_ids:
        message = f"unknown compatible Schema for {asset.id}"
        raise LlmAssetError(message)
    if asset.call_type == CALL_TYPE_SEARCH_INTERPRETATION:
        if asset.output_schema_version_id not in known_search_schema_ids:
            message = f"unknown search interpretation Schema for {asset.id}"
            raise LlmAssetError(message)
    elif asset.output_schema_version_id is not None:
        message = f"job requirement prompt cannot declare a search output Schema: {asset.id}"
        raise LlmAssetError(message)
    content = _read_asset(asset.package, asset.path)
    _verify_hash(content, asset_id=asset.id, expected_sha256=asset.sha256)


def read_requirement_schema(asset_id: str) -> dict[str, object]:
    asset = next((item for item in REQUIREMENT_SCHEMA_ASSETS if item.id == asset_id), None)
    if asset is None:
        message = f"unknown requirement Schema asset: {asset_id}"
        raise LlmAssetError(message)
    content = _read_asset(asset.package, asset.path)
    _verify_hash(content, asset_id=asset.id, expected_sha256=asset.sha256)
    return cast("dict[str, object]", json.loads(content))


def read_requirement_editor_schema(asset_id: str) -> dict[str, object]:
    asset = next((item for item in REQUIREMENT_SCHEMA_ASSETS if item.id == asset_id), None)
    if asset is None or asset.editor_package is None or asset.editor_path is None:
        message = f"unknown requirement editor Schema asset: {asset_id}"
        raise LlmAssetError(message)
    if asset.editor_sha256 is None:
        message = f"missing requirement editor Schema hash: {asset_id}"
        raise LlmAssetError(message)
    content = _read_asset(asset.editor_package, asset.editor_path)
    _verify_hash(
        content,
        asset_id=f"{asset.id}:editor",
        expected_sha256=asset.editor_sha256,
    )
    return cast("dict[str, object]", json.loads(content))


def read_prompt(asset_id: str) -> str:
    asset = next((item for item in PROMPT_ASSETS if item.id == asset_id), None)
    if asset is None:
        message = f"unknown prompt asset: {asset_id}"
        raise LlmAssetError(message)
    content = _read_asset(asset.package, asset.path)
    _verify_hash(content, asset_id=asset.id, expected_sha256=asset.sha256)
    return content.decode("utf-8")


def prompt_asset(asset_id: str) -> PromptAsset:
    asset = next((item for item in PROMPT_ASSETS if item.id == asset_id), None)
    if asset is None:
        message = f"unknown prompt asset: {asset_id}"
        raise LlmAssetError(message)
    return asset


def schema_asset(asset_id: str) -> RequirementSchemaAsset:
    asset = next((item for item in REQUIREMENT_SCHEMA_ASSETS if item.id == asset_id), None)
    if asset is None:
        message = f"unknown requirement Schema asset: {asset_id}"
        raise LlmAssetError(message)
    return asset


def search_interpretation_schema_asset(asset_id: str) -> SearchInterpretationSchemaAsset:
    asset = next(
        (item for item in SEARCH_INTERPRETATION_SCHEMA_ASSETS if item.id == asset_id),
        None,
    )
    if asset is None:
        message = f"unknown search interpretation Schema asset: {asset_id}"
        raise LlmAssetError(message)
    return asset


def read_search_interpretation_schema(asset_id: str) -> dict[str, object]:
    asset = search_interpretation_schema_asset(asset_id)
    content = _read_asset(asset.package, asset.path)
    _verify_hash(content, asset_id=asset.id, expected_sha256=asset.sha256)
    return cast("dict[str, object]", json.loads(content))
