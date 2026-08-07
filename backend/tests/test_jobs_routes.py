"""Route-level tests for /jobs endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

from fastapi import HTTPException
from fastapi import status as http_status
from fastapi.testclient import TestClient

from relationship_network_api import job_service, tenant_audit_service
from relationship_network_api.auth_service import Authentication, MembershipView, UserView
from relationship_network_api.company_service import CompanyArchivedError, CompanyNotFoundError
from relationship_network_api.deps import (
    TenantContext,
    get_authentication,
    get_db_session,
    get_tenant_context,
)
from relationship_network_api.document_text import (
    DocumentTooLargeError,
    InvalidDocumentError,
)
from relationship_network_api.job_service import (
    JobMaterialView,
    JobNotDraftError,
    JobNotFoundError,
    JobStatusConflictError,
    JobView,
)
from relationship_network_api.main import create_app
from relationship_network_api.object_storage_service import ObjectStorageError
from relationship_network_api.routers.jobs import require_jobs_manage
from relationship_network_api.usage_service import QuotaExceededError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from _pytest.monkeypatch import MonkeyPatch
    from sqlalchemy.ext.asyncio import AsyncSession

    from relationship_network_api.models import JobStatus

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
COMPANY_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
JOB_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
MATERIAL_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
NOW = datetime(2026, 8, 6, 12, 0, 0, tzinfo=UTC)


def make_context(*, permissions: frozenset[str]) -> TenantContext:
    membership = MembershipView(
        membership_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        tenant_id=TENANT_ID,
        tenant_name="Acme 科技",
        tenant_slug="acme-1234abcd",
        role="owner",
    )
    return TenantContext(
        authentication=Authentication(
            user=UserView(
                id=USER_ID,
                email="owner@example.com",
                display_name="Tenant Owner",
            ),
            membership=membership,
            expires_at=datetime.now(UTC) + timedelta(days=14),
            renewed=False,
        ),
        membership=membership,
        permissions=permissions,
    )


def make_job_view(*, status: JobStatus = "draft") -> JobView:
    return JobView(
        id=JOB_ID,
        tenant_id=TENANT_ID,
        company_id=COMPANY_ID,
        title="高级后端工程师",
        description="负责 API 与数据管道",
        status=status,
        usage_reservation_id=uuid.uuid4() if status == "active" else None,
        created_at=NOW,
        updated_at=NOW,
        archived_at=NOW if status == "archived" else None,
    )


def make_material_view() -> JobMaterialView:
    return JobMaterialView(
        id=MATERIAL_ID,
        job_id=JOB_ID,
        original_filename="jd.txt",
        content_type="text/plain",
        byte_size=12,
        sha256="0" * 64,
        extracted_text="职位描述",
        scan_status="content_checked",
        uploaded_by=USER_ID,
        created_at=NOW,
    )


def make_client(context: TenantContext | None, *, writable: bool = True) -> TestClient:
    app = create_app(checks=())

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield cast("AsyncSession", cast("object", SimpleNamespace()))

    app.dependency_overrides[get_db_session] = override_session
    if context is None:

        def override_authentication() -> None:
            return None

        app.dependency_overrides[get_authentication] = override_authentication
    else:

        async def override_tenant_context() -> TenantContext:
            return context

        app.dependency_overrides[get_tenant_context] = override_tenant_context

        async def override_writable() -> TenantContext:
            if "jobs:manage" not in context.permissions:
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail="permission_denied",
                )
            if not writable:
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail="subscription_read_only",
                )
            return context

        app.dependency_overrides[require_jobs_manage] = override_writable

    return TestClient(app)


def test_create_job_requires_manage_permission(monkeypatch: MonkeyPatch) -> None:
    client = make_client(make_context(permissions=frozenset({"jobs:read"})))

    async def fail_create(*_args: object, **_kwargs: object) -> JobView:
        msg = "create should not run"
        raise AssertionError(msg)

    monkeypatch.setattr(job_service, "create_job", fail_create)
    response = client.post("/jobs", json={"company_id": str(COMPANY_ID), "title": "A"})
    assert response.status_code == 403
    assert response.json() == {"detail": "permission_denied"}


def test_create_job_allows_manage(monkeypatch: MonkeyPatch) -> None:
    client = make_client(make_context(permissions=frozenset({"jobs:manage"})))

    async def fake_create(*_args: object, **_kwargs: object) -> JobView:
        return make_job_view()

    monkeypatch.setattr(job_service, "create_job", fake_create)
    response = client.post(
        "/jobs",
        json={"company_id": str(COMPANY_ID), "title": "高级后端工程师"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == str(JOB_ID)
    assert body["company_id"] == str(COMPANY_ID)
    assert body["status"] == "draft"


def test_create_job_maps_company_not_found(monkeypatch: MonkeyPatch) -> None:
    client = make_client(make_context(permissions=frozenset({"jobs:manage"})))

    async def missing(*_args: object, **_kwargs: object) -> JobView:
        raise CompanyNotFoundError

    monkeypatch.setattr(job_service, "create_job", missing)
    response = client.post("/jobs", json={"company_id": str(COMPANY_ID), "title": "A"})
    assert response.status_code == 404
    assert response.json() == {"detail": "company_not_found"}


def test_create_job_maps_company_archived(monkeypatch: MonkeyPatch) -> None:
    client = make_client(make_context(permissions=frozenset({"jobs:manage"})))

    async def archived(*_args: object, **_kwargs: object) -> JobView:
        raise CompanyArchivedError

    monkeypatch.setattr(job_service, "create_job", archived)
    response = client.post("/jobs", json={"company_id": str(COMPANY_ID), "title": "A"})
    assert response.status_code == 409
    assert response.json() == {"detail": "company_archived"}


def test_create_job_rejects_read_only_subscription(monkeypatch: MonkeyPatch) -> None:
    client = make_client(
        make_context(permissions=frozenset({"jobs:manage"})),
        writable=False,
    )

    async def fail_create(*_args: object, **_kwargs: object) -> JobView:
        msg = "create should not run"
        raise AssertionError(msg)

    monkeypatch.setattr(job_service, "create_job", fail_create)
    response = client.post("/jobs", json={"company_id": str(COMPANY_ID), "title": "只读"})
    assert response.status_code == 403
    assert response.json() == {"detail": "subscription_read_only"}


def test_list_jobs_passes_filters(monkeypatch: MonkeyPatch) -> None:
    client = make_client(make_context(permissions=frozenset({"jobs:read"})))
    captured: dict[str, object] = {}

    async def fake_list(_session: object, **kwargs: object) -> list[JobView]:
        captured.update(kwargs)
        return [make_job_view(status="active")]

    monkeypatch.setattr(job_service, "list_jobs", fake_list)
    response = client.get(f"/jobs?status=active&company_id={COMPANY_ID}")
    assert response.status_code == 200
    assert captured["status"] == "active"
    assert captured["company_id"] == COMPANY_ID
    assert response.json()[0]["status"] == "active"


def test_get_job_not_found(monkeypatch: MonkeyPatch) -> None:
    client = make_client(make_context(permissions=frozenset({"jobs:read"})))

    async def missing(*_args: object, **_kwargs: object) -> JobView:
        raise JobNotFoundError

    monkeypatch.setattr(job_service, "get_job", missing)
    response = client.get(f"/jobs/{JOB_ID}")
    assert response.status_code == 404
    assert response.json() == {"detail": "job_not_found"}


def test_update_non_draft_job_conflict(monkeypatch: MonkeyPatch) -> None:
    client = make_client(make_context(permissions=frozenset({"jobs:manage"})))

    async def not_draft(*_args: object, **_kwargs: object) -> JobView:
        raise JobNotDraftError

    monkeypatch.setattr(job_service, "update_job", not_draft)
    response = client.patch(f"/jobs/{JOB_ID}", json={"title": "新标题"})
    assert response.status_code == 409
    assert response.json() == {"detail": "job_not_draft"}


def test_activate_job_maps_quota_exceeded(monkeypatch: MonkeyPatch) -> None:
    client = make_client(make_context(permissions=frozenset({"jobs:manage"})))

    async def exceed(*_args: object, **_kwargs: object) -> JobView:
        raise QuotaExceededError

    monkeypatch.setattr(job_service, "activate_job", exceed)
    response = client.post(f"/jobs/{JOB_ID}/activate")
    assert response.status_code == 409
    assert response.json() == {"detail": "job_quota_exceeded"}


def test_activate_job_maps_status_conflict(monkeypatch: MonkeyPatch) -> None:
    client = make_client(make_context(permissions=frozenset({"jobs:manage"})))

    async def conflict(*_args: object, **_kwargs: object) -> JobView:
        raise JobStatusConflictError

    monkeypatch.setattr(job_service, "activate_job", conflict)
    response = client.post(f"/jobs/{JOB_ID}/activate")
    assert response.status_code == 409
    assert response.json() == {"detail": "job_status_conflict"}


def test_activate_job_rejects_read_only_subscription(monkeypatch: MonkeyPatch) -> None:
    client = make_client(
        make_context(permissions=frozenset({"jobs:manage"})),
        writable=False,
    )

    async def fail_activate(*_args: object, **_kwargs: object) -> JobView:
        msg = "activate should not run"
        raise AssertionError(msg)

    monkeypatch.setattr(job_service, "activate_job", fail_activate)
    response = client.post(f"/jobs/{JOB_ID}/activate")
    assert response.status_code == 403
    assert response.json() == {"detail": "subscription_read_only"}


def test_close_job_allows_manage(monkeypatch: MonkeyPatch) -> None:
    client = make_client(make_context(permissions=frozenset({"jobs:manage"})))

    async def fake_close(*_args: object, **_kwargs: object) -> JobView:
        return make_job_view(status="closed")

    monkeypatch.setattr(job_service, "close_job", fake_close)
    response = client.post(f"/jobs/{JOB_ID}/close")
    assert response.status_code == 200
    assert response.json()["status"] == "closed"


def test_close_archived_job_conflict(monkeypatch: MonkeyPatch) -> None:
    client = make_client(make_context(permissions=frozenset({"jobs:manage"})))

    async def conflict(*_args: object, **_kwargs: object) -> JobView:
        raise JobStatusConflictError

    monkeypatch.setattr(job_service, "close_job", conflict)
    response = client.post(f"/jobs/{JOB_ID}/close")
    assert response.status_code == 409
    assert response.json() == {"detail": "job_status_conflict"}


def test_archive_job_allows_manage(monkeypatch: MonkeyPatch) -> None:
    client = make_client(make_context(permissions=frozenset({"jobs:manage"})))

    async def fake_archive(*_args: object, **_kwargs: object) -> JobView:
        return make_job_view(status="archived")

    monkeypatch.setattr(job_service, "archive_job", fake_archive)
    response = client.post(f"/jobs/{JOB_ID}/archive")
    assert response.status_code == 200
    assert response.json()["status"] == "archived"


def test_upload_material_maps_validation_errors(monkeypatch: MonkeyPatch) -> None:
    client = make_client(make_context(permissions=frozenset({"jobs:manage"})))

    async def too_large(*_args: object, **_kwargs: object) -> JobMaterialView:
        raise DocumentTooLargeError

    monkeypatch.setattr(job_service, "upload_material", too_large)
    response = client.post(
        f"/jobs/{JOB_ID}/materials",
        files={"file": ("jd.txt", b"x", "text/plain")},
    )
    assert response.status_code == 413
    assert response.json() == {"detail": "document_too_large"}

    async def invalid(*_args: object, **_kwargs: object) -> JobMaterialView:
        raise InvalidDocumentError

    monkeypatch.setattr(job_service, "upload_material", invalid)
    response = client.post(
        f"/jobs/{JOB_ID}/materials",
        files={"file": ("jd.exe", b"x", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid_document"}


def test_upload_material_maps_storage_failure(monkeypatch: MonkeyPatch) -> None:
    client = make_client(make_context(permissions=frozenset({"jobs:manage"})))

    async def storage_down(*_args: object, **_kwargs: object) -> JobMaterialView:
        msg = "minio unreachable"
        raise ObjectStorageError(msg)

    monkeypatch.setattr(job_service, "upload_material", storage_down)
    response = client.post(
        f"/jobs/{JOB_ID}/materials",
        files={"file": ("jd.txt", b"x", "text/plain")},
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "object_storage_unavailable"}


def test_upload_material_allows_manage(monkeypatch: MonkeyPatch) -> None:
    client = make_client(make_context(permissions=frozenset({"jobs:manage"})))

    async def fake_upload(*_args: object, **_kwargs: object) -> JobMaterialView:
        return make_material_view()

    monkeypatch.setattr(job_service, "upload_material", fake_upload)
    response = client.post(
        f"/jobs/{JOB_ID}/materials",
        files={"file": ("jd.txt", b"job description body", "text/plain")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == str(MATERIAL_ID)
    assert body["job_id"] == str(JOB_ID)
    assert body["scan_status"] == "content_checked"


def test_list_events_requires_read(monkeypatch: MonkeyPatch) -> None:
    client = make_client(make_context(permissions=frozenset({"jobs:manage"})))

    async def fake_get(*_args: object, **_kwargs: object) -> JobView:
        return make_job_view()

    async def fake_events(*_args: object, **_kwargs: object) -> list[object]:
        return []

    monkeypatch.setattr(job_service, "get_job", fake_get)
    monkeypatch.setattr(tenant_audit_service, "list_events_for_target", fake_events)
    response = client.get(f"/jobs/{JOB_ID}/events")
    assert response.status_code == 403
    assert response.json() == {"detail": "permission_denied"}


def test_anonymous_create_rejected() -> None:
    client = make_client(None)
    response = client.post("/jobs", json={"company_id": str(COMPANY_ID), "title": "匿名"})
    assert response.status_code == 401
    assert response.json() == {"detail": "not_authenticated"}
