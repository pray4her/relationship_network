from typing import Final, Literal, TypedDict

from relationship_network_api.celery_app import celery_app

SMOKE_TASK_NAME: Final = "relationship_network.smoke"


class SmokeResult(TypedDict):
    request_id: str
    status: Literal["ok"]


def smoke_payload(request_id: str) -> SmokeResult:
    return SmokeResult(request_id=request_id, status="ok")


smoke = celery_app.task(name=SMOKE_TASK_NAME)(smoke_payload)
