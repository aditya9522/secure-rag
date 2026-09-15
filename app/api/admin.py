"""Platform administrator monitoring and organization provisioning routes."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import system_admin_dep
from app.audit import audit
from app.db_models import AuditEvent, DocumentRecord, Organization, User
from app.models import (
    AuditEventResponse,
    CreateOrganizationRequest,
    OrganizationCreationResponse,
    Principal,
)
from app.services.auth_service import (
    create_organization_with_owner,
    organization_summary,
    user_summary,
)

router = APIRouter(prefix="/v1/admin", tags=["admin"])


def _organization_creation_conflict(exc: Exception) -> HTTPException:
    if isinstance(exc, ValueError):
        return HTTPException(409, str(exc))
    return HTTPException(409, "Organization could not be created")


@router.get("/audit", response_model=list[AuditEventResponse])
async def admin_audit(
    limit: int = 100,
    auth: tuple[Principal, AsyncSession, User] = Depends(system_admin_dep),
):
    _, db, _ = auth
    bounded_limit = max(1, min(limit, 500))
    result = await db.execute(
        select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(bounded_limit)
    )
    return [
        AuditEventResponse(
            id=event.id,
            event_type=event.event_type,
            metadata=event.event_metadata or {},
            user_id=event.user_id,
            created_at=event.created_at,
        )
        for event in result.scalars().all()
    ]


@router.get("/metrics")
async def admin_metrics(
    auth: tuple[Principal, AsyncSession, User] = Depends(system_admin_dep),
):
    _, db, _ = auth
    now = datetime.now(UTC)
    total_users = await db.scalar(select(func.count(User.id)))
    total_organizations = await db.scalar(select(func.count(Organization.id)))
    total_documents = await db.scalar(select(func.count(DocumentRecord.id)))
    events_today = await db.scalar(
        select(func.count(AuditEvent.id)).where(
            AuditEvent.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0)
        )
    )
    return {
        "users": total_users or 0,
        "organizations": total_organizations or 0,
        "documents": total_documents or 0,
        "audit_events_today": events_today or 0,
    }


@router.post("/organizations", response_model=OrganizationCreationResponse)
async def create_organization(
    payload: CreateOrganizationRequest,
    auth: tuple[Principal, AsyncSession, User] = Depends(system_admin_dep),
):
    _, db, system_admin = auth
    try:
        owner, organization, membership = await create_organization_with_owner(
            db,
            system_admin.id,
            payload.name,
            payload.owner_email,
            payload.owner_full_name,
            payload.owner_password,
        )
        db.add(
            AuditEvent(
                organization_id=organization.id,
                user_id=system_admin.id,
                event_type="organization_created",
                event_metadata={"owner_email": owner.email},
            )
        )
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        audit(
            "organization_creation_failed", user_id=str(system_admin.id), error=type(exc).__name__
        )
        raise _organization_creation_conflict(exc) from exc
    except IntegrityError as exc:
        await db.rollback()
        audit(
            "organization_creation_failed", user_id=str(system_admin.id), error=type(exc).__name__
        )
        # Do not expose SQL, schema details, or bound values in an API error.
        raise _organization_creation_conflict(exc) from exc
    audit(
        "organization_created",
        user_id=str(system_admin.id),
        tenant_id=str(organization.id),
        owner_user_id=str(owner.id),
    )
    return OrganizationCreationResponse(
        organization=organization_summary(organization, membership),
        owner=user_summary(owner),
    )
