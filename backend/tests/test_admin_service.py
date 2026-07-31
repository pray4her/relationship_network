import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import cast, final

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from relationship_network_api import admin_service, audit_service
from relationship_network_api.admin_service import (
    TenantNotFoundError,
    get_tenant_detail,
    search_tenants,
    update_tenant_status,
)
from relationship_network_api.models import PlatformAuditEvent, Tenant

pytestmark = pytest.mark.anyio

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
ADMIN_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


@final
class FakeResult:
    def __init__(
        self,
        *,
        scalar: object = None,
        rows: Iterable[object] = (),
        count: int = 0,
    ) -> None:
        self._scalar = scalar
        self._rows = list(rows)
        self._count = count

    def scalar_one_or_none(self) -> object:
        return self._scalar

    def scalar_one(self) -> object:
        return self._scalar if self._scalar is not None else self._count

    def all(self) -> list[object]:
        return self._rows


@final
class SpySession:
    def __init__(self, results: list[FakeResult]) -> None:
        self._results = list(results)
        self.added: list[object] = []
        self.commit_calls = 0
        self.rollback_calls = 0

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def execute(self, _statement: object) -> FakeResult:
        return self._results.pop(0)

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        self.rollback_calls += 1


def as_session(spy: SpySession) -> AsyncSession:
    return cast("AsyncSession", cast("object", spy))


def make_tenant(**overrides: object) -> Tenant:
    tenant = Tenant(id=TENANT_ID, name="Acme 科技", slug="acme-1234abcd")
    tenant.created_at = datetime.now(UTC)
    tenant.status = "active"
    for key, value in overrides.items():
        setattr(tenant, key, value)
    return tenant


async def test_search_tenants_returns_summaries_and_total() -> None:
    # Given a tenant with two active members
    tenant = make_tenant()
    spy = SpySession([FakeResult(), FakeResult(rows=[(tenant, 2)]), FakeResult(count=1)])

    # When tenants are searched
    tenants, total = await search_tenants(as_session(spy), query=None, status=None)

    # Then summaries carry the member count and the total matches
    assert total == 1
    assert len(tenants) == 1
    summary = tenants[0]
    assert summary.id == TENANT_ID
    assert summary.name == "Acme 科技"
    assert summary.status == "active"
    assert summary.member_count == 2


async def test_get_tenant_detail_returns_overview() -> None:
    # Given an existing tenant
    tenant = make_tenant(mfa_required=True)
    spy = SpySession([FakeResult(), FakeResult(scalar=tenant), FakeResult(count=3)])

    # When the detail is loaded
    detail = await get_tenant_detail(as_session(spy), tenant_id=TENANT_ID)

    # Then the full overview is reported
    assert detail.id == TENANT_ID
    assert detail.slug == "acme-1234abcd"
    assert detail.status == "active"
    assert detail.mfa_required
    assert detail.member_count == 3


async def test_get_tenant_detail_raises_for_unknown_tenant() -> None:
    # Given no matching tenant
    spy = SpySession([FakeResult(), FakeResult(scalar=None)])

    # When the detail is loaded
    with pytest.raises(TenantNotFoundError):
        _ = await get_tenant_detail(as_session(spy), tenant_id=TENANT_ID)


async def test_update_tenant_status_audits_success() -> None:
    # Given an active tenant and a platform admin actor
    tenant = make_tenant()
    spy = SpySession([FakeResult(), FakeResult(scalar=tenant), FakeResult(count=1)])

    # When the tenant is suspended
    view = await admin_service.update_tenant_status(
        as_session(spy),
        tenant_id=TENANT_ID,
        status="suspended",
        actor_id=ADMIN_ID,
    )

    # Then the change is committed with a success audit event
    assert tenant.status == "suspended"
    assert view.status == "suspended"
    assert spy.commit_calls == 1
    event = next(i for i in spy.added if isinstance(i, PlatformAuditEvent))
    assert event.actor_id == ADMIN_ID
    assert event.action == admin_service.TENANT_STATUS_UPDATE_ACTION
    assert event.target_type == "tenant"
    assert event.target_id == str(TENANT_ID)
    assert event.result == audit_service.AUDIT_RESULT_SUCCESS


async def test_update_tenant_status_audits_failure_for_unknown_tenant() -> None:
    # Given no matching tenant
    spy = SpySession([FakeResult(), FakeResult(scalar=None)])

    # When a status change is attempted
    with pytest.raises(TenantNotFoundError):
        _ = await update_tenant_status(
            as_session(spy),
            tenant_id=TENANT_ID,
            status="suspended",
            actor_id=ADMIN_ID,
        )

    # Then the failed attempt is still audited and persisted
    assert spy.commit_calls == 1
    event = next(i for i in spy.added if isinstance(i, PlatformAuditEvent))
    assert event.result == audit_service.AUDIT_RESULT_FAILURE
    assert event.detail == admin_service.TENANT_NOT_FOUND_DETAIL
