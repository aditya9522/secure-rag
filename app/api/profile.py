"""Current-user profile and notification routes."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import authorized_principal_dep, principal_dep, principal_uuid
from app.db import get_db
from app.db_models import AuditEvent, RefreshSession, User
from app.models import (
    MeResponse,
    NotificationResponse,
    Principal,
    UpdateProfileRequest,
)
from app.security.passwords import hash_password, verify_password
from app.services.auth_service import active_membership, build_auth_response, user_summary

router = APIRouter(prefix="/v1", tags=["profile"])


@router.get("/me", response_model=MeResponse)
async def me(
    principal: Principal = Depends(principal_dep),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    user_id = principal_uuid(principal)
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "User account is inactive")
    try:
        organization, membership = await active_membership(db, user.id, UUID(principal.tenant_id))
    except (ValueError, AttributeError) as exc:
        raise HTTPException(403, "Organization membership is no longer active") from exc
    _, current_org, organizations = await build_auth_response(db, user, organization, membership)
    return MeResponse(
        user=user_summary(user), current_organization=current_org, organizations=organizations
    )


@router.patch("/me", response_model=MeResponse)
async def update_me(
    payload: UpdateProfileRequest,
    principal: Principal = Depends(authorized_principal_dep),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    user_id = principal_uuid(principal)
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "User account is inactive")
    if payload.new_password:
        if not payload.current_password or not verify_password(
            payload.current_password, user.password_hash
        ):
            raise HTTPException(400, "Current password is incorrect")
        user.password_hash = hash_password(payload.new_password)
        await db.execute(
            RefreshSession.__table__.update()
            .where(RefreshSession.user_id == user.id)
            .values(revoked_at=datetime.now(UTC))
        )
    if payload.full_name:
        user.full_name = payload.full_name.strip()
    db.add(
        AuditEvent(
            organization_id=UUID(principal.tenant_id),
            user_id=user.id,
            event_type="profile_updated",
            event_metadata={"password_changed": payload.new_password is not None},
        )
    )
    await db.commit()
    organization, membership = await active_membership(db, user.id, UUID(principal.tenant_id))
    _, current_org, organizations = await build_auth_response(db, user, organization, membership)
    return MeResponse(
        user=user_summary(user), current_organization=current_org, organizations=organizations
    )


@router.get("/notifications", response_model=list[NotificationResponse])
async def list_notifications(
    limit: int = 20,
    principal: Principal = Depends(authorized_principal_dep),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """Return safe, tenant-scoped activity summaries for the workspace UI."""
    organization_id = UUID(principal.tenant_id)
    user_id = principal_uuid(principal)
    relevant_events = {
        "document_ingested",
        "document_revoked",
        "document_ingest_failed",
        "member_invited",
        "member_access_updated",
        "organization_created",
        "profile_updated",
        "refresh_reuse_detected",
    }
    result = await db.execute(
        select(AuditEvent)
        .where(
            AuditEvent.organization_id == organization_id,
            AuditEvent.event_type.in_(relevant_events),
            (AuditEvent.user_id == user_id)
            | (
                AuditEvent.event_type.in_(
                    {
                        "document_ingested",
                        "document_revoked",
                        "document_ingest_failed",
                        "member_invited",
                        "member_access_updated",
                        "organization_created",
                    }
                )
            ),
        )
        .order_by(AuditEvent.created_at.desc())
        .limit(max(1, min(limit, 50)))
    )
    copy = {
        "document_ingested": (
            "Source indexed",
            "A governed source is available for authorized retrieval.",
            "success",
        ),
        "document_revoked": (
            "Source revoked",
            "A source was removed from future retrieval.",
            "warning",
        ),
        "document_ingest_failed": (
            "Source indexing failed",
            "A source could not be made available.",
            "warning",
        ),
        "member_invited": ("Member invited", "An organization invitation was created.", "info"),
        "member_access_updated": (
            "Access updated",
            "Organization member access was changed.",
            "info",
        ),
        "organization_created": (
            "Organization created",
            "A new organization and owner account were created.",
            "success",
        ),
        "profile_updated": ("Profile updated", "Your account profile was updated.", "success"),
        "refresh_reuse_detected": (
            "Session security alert",
            "A reused refresh session was revoked.",
            "warning",
        ),
    }
    return [
        NotificationResponse(
            id=event.id,
            event_type=event.event_type,
            title=copy[event.event_type][0],
            detail=copy[event.event_type][1],
            severity=copy[event.event_type][2],
            created_at=event.created_at,
        )
        for event in result.scalars().all()
    ]
