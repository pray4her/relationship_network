from typing import Annotated, ClassVar, Final, Literal, TypeGuard, cast, final

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from relationship_network_api.llm_assets.manifest import (
    JOB_REQUIREMENT_SCHEMA_V1,
    JOB_REQUIREMENT_SCHEMA_V2,
)

SEARCH_CONTRACT_VERSION_V1: Final = "v1"
EXECUTABLE_SCHEMA_VERSIONS: Final[tuple[str, str]] = (
    JOB_REQUIREMENT_SCHEMA_V1.id,
    JOB_REQUIREMENT_SCHEMA_V2.id,
)
AUTHORIZATION_HEADER: Final = "Authorization"
CONTRACT_VERSION_HEADER: Final = "X-Search-Contract-Version"
REQUEST_ID_HEADER: Final = "X-Request-Id"
HEALTH_PATH: Final = "/v1/health"
PERSON_DETAIL_PATH_TEMPLATE: Final = "/v1/persons/{canonical_person_id}"
PERSON_BATCH_PATH: Final = "/v1/persons/batch"
PERSON_EVIDENCE_PATH_TEMPLATE: Final = "/v1/persons/{canonical_person_id}/evidence"
BEARER_SCHEME: Final = "Bearer"
MAX_PERSON_BATCH_SIZE: Final = 500
TALENT_SEARCH_PATH: Final = "/v1/search"
MIN_SEARCH_HIT_LIMIT: Final = 1
MAX_SEARCH_HIT_LIMIT: Final = 500
DEFAULT_SEARCH_HIT_LIMIT: Final = MAX_SEARCH_HIT_LIMIT
MAX_HARD_CONDITIONS: Final = 100
MAX_RESEARCH_TOPIC_QUERY_CHARACTERS: Final = JOB_REQUIREMENT_SCHEMA_V1.output_limits[
    "research_topic_query_characters"
]
BETWEEN_VALUE_ITEM_COUNT: Final = 2
MAX_ENUM_IN_VALUES: Final = 50
HARD_CONDITION_FIELD_CATALOG: Final[dict[str, frozenset[str]]] = {
    "qs_top200_rank": frozenset({"gte", "lte", "between"}),
    "world_top500_rank": frozenset({"gte", "lte", "between"}),
    "h_index": frozenset({"gte", "lte", "between"}),
    "total_citations": frozenset({"gte", "lte", "between"}),
    "chinese_identity": frozenset({"eq", "in"}),
    "country": frozenset({"eq", "in"}),
    "current_affiliation": frozenset({"match", "match_phrase"}),
}
NUMERIC_CONDITION_FIELDS: Final[frozenset[str]] = frozenset(
    {"qs_top200_rank", "world_top500_rank", "h_index", "total_citations"}
)

type SearchBaseErrorCategory = Literal[
    "unauthenticated",
    "forbidden",
    "contract_version_incompatible",
    "invalid_query",
    "timeout",
    "network_error",
    "rate_limited",
    "unavailable",
    "invalid_response",
]
type ChineseIdentity = Literal["国内华人", "海外华人", "外国人"]
type ProvenanceField = Literal[
    "display_name",
    "current_affiliation",
    "country",
    "chinese_identity",
    "h_index",
    "total_citations",
    "qs_top200_rank",
    "world_top500_rank",
    "has_contact",
]
type ProvenanceSourceKind = Literal["publication", "profile"]
type HardConditionValue = int | float | str | list[int | float] | list[str]

CHINESE_IDENTITY_VALUES: Final[tuple[ChineseIdentity, ...]] = (
    "国内华人",
    "海外华人",
    "外国人",
)
PROVENANCE_FIELDS: Final[tuple[ProvenanceField, ...]] = (
    "display_name",
    "current_affiliation",
    "country",
    "chinese_identity",
    "h_index",
    "total_citations",
    "qs_top200_rank",
    "world_top500_rank",
    "has_contact",
)


@final
class SearchBaseHealthResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore", frozen=True)

    request_id: str = Field(min_length=1)
    contract_version: str = Field(min_length=1)
    executable_schema_versions: tuple[str, ...] = Field(min_length=1)
    data_version: str = Field(min_length=1)
    status: Literal["ok"] = "ok"


@final
class SearchBaseErrorBody(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore", frozen=True)

    category: SearchBaseErrorCategory
    retryable: bool


@final
class CanonicalPersonFields(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore", frozen=True)

    canonical_person_id: str = Field(min_length=1)
    historical_source_ids: tuple[str, ...]
    display_name: str = Field(min_length=1)
    current_affiliation: str = Field(min_length=1)
    country: str = Field(min_length=1)
    chinese_identity: ChineseIdentity
    h_index: int = Field(ge=0)
    total_citations: int = Field(ge=0)
    qs_top200_rank: int | None = None
    world_top500_rank: int | None = None
    has_contact: bool | None = None


@final
class PersonDetailFound(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore", frozen=True)

    outcome: Literal["found"]
    request_id: str = Field(min_length=1)
    data_version: str = Field(min_length=1)
    person: CanonicalPersonFields


@final
class PersonCurrentAbsence(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore", frozen=True)

    outcome: Literal["current_absence"]
    request_id: str = Field(min_length=1)
    data_version: str = Field(min_length=1)
    canonical_person_id: str = Field(min_length=1)


type PersonDetailResult = PersonDetailFound | PersonCurrentAbsence

PERSON_DETAIL_RESPONSE_ADAPTER: Final[TypeAdapter[PersonDetailResult]] = TypeAdapter(
    Annotated[PersonDetailFound | PersonCurrentAbsence, Field(discriminator="outcome")]
)


@final
class PersonBatchRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore", frozen=True)

    canonical_person_ids: list[str] = Field(max_length=MAX_PERSON_BATCH_SIZE)


@final
class PersonBatchResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore", frozen=True)

    request_id: str = Field(min_length=1)
    data_version: str = Field(min_length=1)
    persons: tuple[CanonicalPersonFields, ...]
    currently_absent_ids: tuple[str, ...]


@final
class PersonPublication(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore", frozen=True)

    publication_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    year: int = Field(ge=0)
    venue: str = Field(min_length=1)
    snippet: str | None = None


@final
class FieldProvenanceClaim(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore", frozen=True)

    field: ProvenanceField
    source_kind: ProvenanceSourceKind
    source_id: str = Field(min_length=1)
    snippet: str | None = None


@final
class PersonEvidenceFound(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore", frozen=True)

    outcome: Literal["found"]
    request_id: str = Field(min_length=1)
    data_version: str = Field(min_length=1)
    canonical_person_id: str = Field(min_length=1)
    publications: tuple[PersonPublication, ...]
    field_provenance: tuple[FieldProvenanceClaim, ...]


type PersonEvidenceResult = PersonEvidenceFound | PersonCurrentAbsence

PERSON_EVIDENCE_RESPONSE_ADAPTER: Final[TypeAdapter[PersonEvidenceResult]] = TypeAdapter(
    Annotated[PersonEvidenceFound | PersonCurrentAbsence, Field(discriminator="outcome")]
)


@final
class HardCondition(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    field: str = Field(min_length=1)
    operator: str = Field(min_length=1)
    value: HardConditionValue


@final
class TalentSearchRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    hard_conditions: tuple[HardCondition, ...] = Field(default=(), max_length=MAX_HARD_CONDITIONS)
    research_topic_query: str = Field(default="", max_length=MAX_RESEARCH_TOPIC_QUERY_CHARACTERS)
    hit_limit: int = Field(
        default=DEFAULT_SEARCH_HIT_LIMIT,
        ge=MIN_SEARCH_HIT_LIMIT,
        le=MAX_SEARCH_HIT_LIMIT,
    )

    @field_validator("research_topic_query", mode="before")
    @classmethod
    def _strip_research_topic_query(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def _validate_search_request(self) -> "TalentSearchRequest":
        for condition in self.hard_conditions:
            _validate_hard_condition_catalog(condition)
        if not self.hard_conditions and not self.research_topic_query:
            message = "hard_conditions and research_topic_query must not both be empty"
            raise ValueError(message)
        return self

    @property
    def has_research_topic(self) -> bool:
        return bool(self.research_topic_query)


@final
class SearchHit(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore", frozen=True)

    person: CanonicalPersonFields
    hit_publications: tuple[PersonPublication, ...]
    semantic_score: float | None = None


@final
class TalentSearchResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore", frozen=True)

    request_id: str = Field(min_length=1)
    data_version: str = Field(min_length=1)
    hits: tuple[SearchHit, ...]


def _is_non_negative_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def _is_between_value(value: object) -> bool:
    if not isinstance(value, list):
        return False
    items = cast("list[object]", value)
    return len(items) == BETWEEN_VALUE_ITEM_COUNT and all(
        isinstance(item, (int, float)) and not isinstance(item, bool) and item >= 0
        for item in items
    )


def _is_non_blank_string(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and bool(value.strip())


def _is_string_list(value: object) -> TypeGuard[list[str]]:
    if not isinstance(value, list):
        return False
    items = cast("list[object]", value)
    if not 1 <= len(items) <= MAX_ENUM_IN_VALUES:
        return False
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, str) or not item.strip():
            return False
        seen.add(item)
    return len(seen) == len(items)


def _validate_hard_condition_catalog(condition: HardCondition) -> None:
    operators = HARD_CONDITION_FIELD_CATALOG.get(condition.field)
    if operators is None:
        message = f"unknown hard-condition field: {condition.field}"
        raise ValueError(message)
    if condition.operator not in operators:
        message = f"operator {condition.operator!r} not allowed for field {condition.field!r}"
        raise ValueError(message)
    if condition.field in NUMERIC_CONDITION_FIELDS:
        _validate_numeric_condition_value(condition)
    elif condition.field in ("chinese_identity", "country"):
        _validate_enum_condition_value(condition)
    else:
        _validate_affiliation_condition_value(condition)


def _validate_numeric_condition_value(condition: HardCondition) -> None:
    value = condition.value
    if condition.operator in ("gte", "lte") and not _is_non_negative_number(value):
        message = "numeric threshold value must be a non-negative number"
        raise ValueError(message)
    if condition.operator == "between" and not _is_between_value(value):
        message = "between value must be exactly two non-negative numbers"
        raise ValueError(message)


def _validate_enum_condition_value(condition: HardCondition) -> None:
    value = condition.value
    if condition.operator == "eq":
        if not _is_non_blank_string(value):
            message = "enum eq value must be a non-empty string"
            raise ValueError(message)
        if condition.field == "chinese_identity" and value not in CHINESE_IDENTITY_VALUES:
            message = "illegal chinese_identity value"
            raise ValueError(message)
    elif condition.operator == "in":
        if not _is_string_list(value):
            message = "enum in value must be a non-empty list of unique strings"
            raise ValueError(message)
        if condition.field == "chinese_identity" and any(
            item not in CHINESE_IDENTITY_VALUES for item in value
        ):
            message = "illegal chinese_identity value"
            raise ValueError(message)


def _validate_affiliation_condition_value(condition: HardCondition) -> None:
    if not _is_non_blank_string(condition.value):
        message = "affiliation value must be a non-empty string"
        raise ValueError(message)
