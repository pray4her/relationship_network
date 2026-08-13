from typing import Annotated, ClassVar, Final, Literal, final

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

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
BEARER_SCHEME: Final = "Bearer"
MAX_PERSON_BATCH_SIZE: Final = 500

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

CHINESE_IDENTITY_VALUES: Final[tuple[ChineseIdentity, ...]] = (
    "国内华人",
    "海外华人",
    "外国人",
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
