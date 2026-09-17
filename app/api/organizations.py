"""Organization context and membership administration routes."""

import hashlib
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import (
    attach_refresh_cookie,
    build_auth_response_for_session,
    validate_cookie_request_origin,
)
from app.api.dependencies import (
    authorized_principal_dep,
    org_admin_dep,
    principal_uuid,
    set_tenant_context,
)
from app.db import get_db
from app.db_models import (
    AuditEvent,
    Membership,
    MembershipStatus,
    OrganizationRole,
    RefreshSession,
    User,
)
from app.models import (
    AuthResponse,
    InvitationResponse,
    InviteMemberRequest,
    Principal,
    SwitchOrganizationRequest,
    UpdateMemberRequest,
)
from app.services.auth_service import (
    active_membership,
    create_invitation,
    issue_refresh_session,
    normalize_email,
)

router = APIRouter(prefix="/v1/organizations", tags=["organizations"])


def _assert_can_grant_role(
    acting_role: str, requested_role: str, current_role: str | None = None
) -> None:
    if (
        acting_role != OrganizationRole.owner.value
        and requested_role == OrganizationRole.admin.value
        and current_role != OrganizationRole.admin.value
    ):
        raise HTTPException(403, "Only organization owners can grant administrator access")


@router.post("/switch", response_model=AuthResponse)
async def switch_organization(
    request: Request,
    payload: SwitchOrganizationRequest,
    principal: Principal = Depends(authorized_principal_dep),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    validate_cookie_request_origin(request)
    user_id = principal_uuid(principal)
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "User account is inactive")
    try:
        organization, membership = await active_membership(db, user.id, payload.organization_id)
    except ValueError as exc:
        raise HTTPException(403, "You are not an active member of that organization") from exc
    await set_tenant_context(
        db,
        Principal(
            user_id=str(user.id),
            tenant_id=str(organization.id),
            groups=membership.groups or [],
            classification_max=membership.classification_max,
            can_manage_access=membership.role
            in {OrganizationRole.owner.value, OrganizationRole.admin.value},
        ),
        system_admin=user.is_system_admin,
    )
    db.add(
        AuditEvent(
            organization_id=organization.id,
            user_id=user.id,
            event_type="organization_switched",
            event_metadata={},
        )
    )
    refresh_token: str | None = None
    raw_refresh = request.cookies.get("refresh_token")
    if raw_refresh:
        refresh_session = await db.scalar(
            select(RefreshSession)
            .where(
                RefreshSession.user_id == user.id,
                RefreshSession.token_hash == hashlib.sha256(raw_refresh.encode()).hexdigest(),
                RefreshSession.revoked_at.is_(None),
                RefreshSession.expires_at > datetime.now(UTC),
            )
            .with_for_update()
        )
        if refresh_session:
            refresh_session.revoked_at = datetime.now(UTC)
            refresh_token = await issue_refresh_session(db, user, organization.id)
    await db.commit()
    response = JSONResponse(
        (await build_auth_response_for_session(db, user, organization, membership)).model_dump(
            mode="json"
        )
    )
    return attach_refresh_cookie(response, refresh_token) if refresh_token else response


@router.post("/invitations", response_model=InvitationResponse)
async def invite_member(
    payload: InviteMemberRequest,
    auth: tuple[Principal, AsyncSession, Membership] = Depends(org_admin_dep),
):
    principal, db, acting_membership = auth
    organization_id = UUID(principal.tenant_id)
    _assert_can_grant_role(acting_membership.role, payload.role)
    try:
        invitation, raw_token = await create_invitation(
            db,
            organization_id,
            payload.email,
            payload.full_name,
            payload.role,
            payload.groups,
            payload.classification_max,
        )
        db.add(
            AuditEvent(
                organization_id=organization_id,
                user_id=principal_uuid(principal),
                event_type="member_invited",
                event_metadata={"email": normalize_email(payload.email), "role": payload.role},
            )
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "An invitation for this member could not be created") from exc
    return InvitationResponse(
        invitation_id=invitation.id, invitation_token=raw_token, expires_at=invitation.expires_at
    )


@router.get("/members")
async def list_members(
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0, le=1_000_000),
    auth: tuple[Principal, AsyncSession, Membership] = Depends(org_admin_dep),
):
    principal, db, _ = auth
    organization_id = UUID(principal.tenant_id)
    result = await db.execute(
        select(User, Membership)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.organization_id == organization_id)
        .order_by(User.full_name)
        .offset(offset)
        .limit(limit)
    )
    return [
        {
            "user_id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": membership.role,
            "status": membership.status,
            "groups": membership.groups or [],
            "classification_max": membership.classification_max,
            "created_at": membership.created_at,
        }
        for user, membership in result.all()
    ]


@router.patch("/members/{member_id}")
async def update_member(
    member_id: UUID,
    payload: UpdateMemberRequest,
    auth: tuple[Principal, AsyncSession, Membership] = Depends(org_admin_dep),
):
    principal, db, acting_membership = auth
    organization_id = UUID(principal.tenant_id)
    result = await db.execute(
        select(Membership).where(
            Membership.user_id == member_id, Membership.organization_id == organization_id
        )
    )
    membership = result.scalar_one_or_none()
    if not membership or membership.role == OrganizationRole.owner.value:
        raise HTTPException(404, "Member not found")
    if member_id == principal_uuid(principal) and payload.role == MembershipStatus.suspended.value:
        raise HTTPException(400, "You cannot suspend your own account")
    _assert_can_grant_role(acting_membership.role, payload.role, membership.role)
    membership.role = (
        payload.role if payload.role != MembershipStatus.suspended.value else membership.role
    )
    membership.status = (
        MembershipStatus.suspended.value
        if payload.role == MembershipStatus.suspended.value
        else MembershipStatus.active.value
    )
    membership.groups = sorted(set(payload.groups))
    membership.classification_max = payload.classification_max.value
    db.add(
        AuditEvent(
            organization_id=organization_id,
            user_id=principal_uuid(principal),
            event_type="member_access_updated",
            event_metadata={"member_id": str(member_id), "status": membership.status},
        )
    )
    await db.commit()
    return {"status": "updated"}
