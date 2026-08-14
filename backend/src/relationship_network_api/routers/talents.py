"""HTTP routes for reading the shared local talent master."""

from __future__ import annotations

import uuid  # noqa: TC003 (pydantic resolves model annotations at runtime)
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import talent_identity_service
from relationship_network_api.auth_service import Authentication
from relationship_network_api.deps import get_db_session, require_authentication
from relationship_network_api.models import ChineseIdentity, TalentAvailability  # noqa: TC001
from relationship_network_api.talent_identity_service import (
    TALENT_NOT_FOUND_DETAIL,
    LocalTalentView,
    TalentNotFoundError,
)

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
AuthDep = Annotated[Authentication, Depends(require_authentication)]


class TalentResponse(BaseModel):
    id: uuid.UUID
    canonical_person_id: str
    display_name: str
    current_affiliation: str
    country: str
    chinese_identity: ChineseIdentity
    h_index: int
    total_citations: int
    qs_top200_rank: int | None
    world_top500_rank: int | None
    has_contact: bool | None
    data_version: str
    availability: TalentAvailability
    last_synced_at: str
    historical_source_ids: tuple[str, ...]


def talent_response(view: LocalTalentView) -> TalentResponse:
    return TalentResponse(
        id=view.id,
        canonical_person_id=view.canonical_person_id,
        display_name=view.display_name,
        current_affiliation=view.current_affiliation,
        country=view.country,
        chinese_identity=view.chinese_identity,
        h_index=view.h_index,
        total_citations=view.total_citations,
        qs_top200_rank=view.qs_top200_rank,
        world_top500_rank=view.world_top500_rank,
        has_contact=view.has_contact,
        data_version=view.data_version,
        availability=view.availability,
        last_synced_at=view.last_synced_at.isoformat(),
        historical_source_ids=view.historical_source_ids,
    )


@router.get("/talents/{local_talent_id}")
async def get_talent(
    local_talent_id: uuid.UUID,
    _auth: AuthDep,
    session: DbSession,
) -> TalentResponse:
    try:
        view = await talent_identity_service.get_talent(
            session,
            local_talent_id=local_talent_id,
        )
    except TalentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=TALENT_NOT_FOUND_DETAIL,
        ) from error
    return talent_response(view)
