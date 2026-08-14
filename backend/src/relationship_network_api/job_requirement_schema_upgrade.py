"""Deterministic, versioned converters for explicit requirement draft schema upgrades.

Converters never call an LLM: the same input document always produces the same
converted document, the same per-item upgrade mappings, and the same pending
upgrade items. Anything that cannot be converted losslessly is excluded from
the converted document and reported as a pending upgrade item that a member
must resolve manually before the draft can be confirmed.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Final, cast, final

from relationship_network_api.llm_assets import manifest

CONVERTER_V1_TO_V2: Final = "v1-to-v2@1"

KIND_HARD_CONDITION: Final = "hard_condition"
KIND_PREFERENCE_CONDITION: Final = "preference_condition"
_MAPPING_COPIED: Final = "copied"
_MAPPING_UNCONVERTIBLE: Final = "unconvertible_chinese_identity"
_CONDITION_LISTS: Final = (
    ("hard_conditions", KIND_HARD_CONDITION),
    ("preference_conditions", KIND_PREFERENCE_CONDITION),
)


@final
@dataclass(frozen=True)
class SchemaConversion:
    """Outcome of one deterministic conversion over an editable draft document."""

    document: dict[str, object]
    item_mappings: list[dict[str, object]]
    lossy_items: list[dict[str, object]]


def converter_version_for(from_schema_id: str, to_schema_id: str) -> str | None:
    """Return the registered converter version for a schema pair, if any."""
    if (
        from_schema_id == manifest.JOB_REQUIREMENT_SCHEMA_V1.id
        and to_schema_id == manifest.JOB_REQUIREMENT_SCHEMA_V2.id
    ):
        return CONVERTER_V1_TO_V2
    return None


def convert_document(
    document: dict[str, object],
    *,
    from_schema_id: str,
    to_schema_id: str,
) -> SchemaConversion:
    """Convert an editable draft document with the registered converter."""
    converter = converter_version_for(from_schema_id, to_schema_id)
    if converter is None:
        message = f"no deterministic converter: {from_schema_id} -> {to_schema_id}"
        raise ValueError(message)
    return _convert_v1_to_v2(document)


def _convert_v1_to_v2(document: dict[str, object]) -> SchemaConversion:
    """Copy every item; only out-of-catalog chinese_identity values are lossy.

    V2 tightens chinese_identity values to the deployed catalog enum. Every
    other field, operator, and constraint is identical between V1 and V2, so
    the conversion is a lossless copy for all other items.
    """
    allowed = set(manifest.JOB_REQUIREMENT_SCHEMA_V2.chinese_identity_values)
    converted = deepcopy(document)
    item_mappings: list[dict[str, object]] = []
    lossy_items: list[dict[str, object]] = []
    for list_key, kind in _CONDITION_LISTS:
        kept: list[object] = []
        for item in cast("list[dict[str, object]]", document[list_key]):
            item_id = cast("str", item["item_id"])
            if _converts_losslessly(item, allowed=allowed):
                kept.append(deepcopy(item))
                item_mappings.append(
                    {"item_id": item_id, "kind": kind, "mapping": _MAPPING_COPIED, "lossless": True}
                )
            else:
                item_mappings.append(
                    {
                        "item_id": item_id,
                        "kind": kind,
                        "mapping": _MAPPING_UNCONVERTIBLE,
                        "lossless": False,
                    }
                )
                lossy_items.append({"item_id": item_id, "kind": kind, "snapshot": deepcopy(item)})
        converted[list_key] = kept
    return SchemaConversion(
        document=converted,
        item_mappings=item_mappings,
        lossy_items=lossy_items,
    )


def _converts_losslessly(item: dict[str, object], *, allowed: set[str]) -> bool:
    if item["field"] != "chinese_identity":
        return True
    if item["operator"] == "eq":
        return item["value"] in allowed
    values = cast("list[object]", item["value"])
    return len(values) <= len(allowed) and all(value in allowed for value in values)
