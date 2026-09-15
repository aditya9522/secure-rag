"""Shared authentication, authorization, and request-boundary dependencies."""

from uuid import UUID

from fastapi import Depends, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.db_models import Membership, MembershipStatus, OrganizationRole, User
from app.models import Principal
from app.security.auth import bearer, get_principal


def principal_uuid(principal: Principal) -> UUID:
    try:
        return UUID(principal.user_id)
    except ValueError as exc:
        raise HTTPException(401, "Invalid authorization claims") from exc


async def set_tenant_context(
    db: AsyncSession, principal: Principal, *, system_admin: bool = False
) -> None:
    """Set transaction-local context consumed by PostgreSQL row-level policies."""
    await db.execute(
        text(
            """
            SELECT set_config('app.current_user_id', :user_id, true),
                   set_config('app.current_organization_id', :organization_id, true),
                   set_config('app.is_system_admin', :is_system_admin, true)
            """
        ),
        {
            "user_id": principal.user_id,
            "organization_id": principal.tenant_id,
            "is_system_admin": "true" if system_admin else "false",
        },
    )


def principal_dep(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),  # noqa: B008
) -> Principal:
    return get_principal(credentials)


async def authorized_principal_dep(
    principal: Principal = Depends(principal_dep),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Principal:
    """Refresh tenant claims from PostgreSQL so membership revocation is immediate."""
    user_id = principal_uuid(principal)
    try:
        organization_id = UUID(principal.tenant_id)
    except ValueError as exc:
        raise HTTPException(401, "Invalid organization claims") from exc
    await set_tenant_context(db, principal)
    result = await db.execute(
        select(User, Membership)
        .join(Membership, Membership.user_id == User.id)
        .where(
            User.id == user_id,
            User.is_active.is_(True),
            Membership.organization_id == organization_id,
            Membership.status == MembershipStatus.active.value,
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(403, "Active organization membership required")
    user, membership = row
    return Principal(
        user_id=str(user.id),
        tenant_id=str(organization_id),
        groups=membership.groups or [],
        classification_max=membership.classification_max,
        can_manage_access=user.is_system_admin
        or membership.role in {OrganizationRole.owner.value, OrganizationRole.admin.value},
    )


async def org_admin_dep(
    principal: Principal = Depends(authorized_principal_dep),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> tuple[Principal, AsyncSession, Membership]:
    user_id = principal_uuid(principal)
    try:
        organization_id = UUID(principal.tenant_id)
    except ValueError as exc:
        raise HTTPException(401, "Invalid organization claims") from exc
    result = await db.execute(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.organization_id == organization_id,
            Membership.status == MembershipStatus.active.value,
            Membership.role.in_([OrganizationRole.owner.value, OrganizationRole.admin.value]),
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(403, "Organization administrator access required")
    return principal, db, membership


async def system_admin_dep(
    principal: Principal = Depends(principal_dep),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> tuple[Principal, AsyncSession, User]:
    user_id = principal_uuid(principal)
    user = await db.get(User, user_id)
    if not user or not user.is_active or not user.is_system_admin:
        raise HTTPException(403, "System administrator access required")
    await set_tenant_context(db, principal, system_admin=True)
    return principal, db, user


def auth_ready() -> None:
    if settings.require_auth and not settings.jwt_secret_configured:
        raise HTTPException(503, "Authentication is not configured")


async def read_upload_bounded(file: UploadFile) -> bytes:
    parts: list[bytes] = []
    total = 0
    while True:
        part = await file.read(64 * 1024)
        if not part:
            break
        total += len(part)
        if total > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="Document too large")
        parts.append(part)
    return b"".join(parts)
