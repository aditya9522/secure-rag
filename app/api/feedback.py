"""Authenticated feedback submission and platform-admin review routes."""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import authorized_principal_dep, principal_uuid, system_admin_dep
from app.audit import audit
from app.config import settings
from app.core import runtime
from app.db import get_db
from app.db_models import (
    AuditEvent,
    Feedback,
    FeedbackPriority,
    FeedbackStatus,
    Organization,
    User,
    utc_now,
)
from app.models import (
    CreateFeedbackRequest,
    FeedbackAdminResponse,
    FeedbackResponse,
    Principal,
    UpdateFeedbackRequest,
)

router = APIRouter(tags=["feedback"])


def _feedback_response(feedback: Feedback) -> FeedbackResponse:
    return FeedbackResponse(
        id=feedback.id,
        organization_id=feedback.organization_id,
        user_id=feedback.user_id,
        reporter_name=feedback.reporter_name,
        reporter_email=feedback.reporter_email,
        category=feedback.category,
        subject=feedback.subject,
        message=feedback.message,
        rating=feedback.rating,
        source_page=feedback.source_page,
        status=feedback.status,
        priority=feedback.priority,
        created_at=feedback.created_at,
        updated_at=feedback.updated_at,
    )


def _admin_feedback_response(feedback: Feedback, organization_name: str) -> FeedbackAdminResponse:
    return FeedbackAdminResponse(
        **_feedback_response(feedback).model_dump(),
        organization_name=organization_name,
        admin_note=feedback.admin_note,
    )


@router.post("/v1/feedback", response_model=FeedbackResponse, status_code=201)
@runtime.limiter.limit(f"{max(1, settings.rate_limit_per_minute // 2)}/minute")
async def create_feedback(
    request: Request,
    payload: CreateFeedbackRequest,
    principal: Principal = Depends(authorized_principal_dep),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    user = await db.get(User, principal_uuid(principal))
    if not user or not user.is_active:
        raise HTTPException(401, "User account is inactive")
    feedback = Feedback(
        id=uuid4(),
        organization_id=UUID(principal.tenant_id),
        user_id=user.id,
        reporter_name=user.full_name,
        reporter_email=user.email,
        category=payload.category,
        subject=payload.subject,
        message=payload.message,
        rating=payload.rating,
        source_page=payload.source_page,
        status=FeedbackStatus.new.value,
        priority=FeedbackPriority.normal.value,
    )
    db.add(feedback)
    db.add(
        AuditEvent(
            organization_id=feedback.organization_id,
            user_id=user.id,
            event_type="feedback_submitted",
            event_metadata={"feedback_id": str(feedback.id), "category": feedback.category},
        )
    )
    await db.commit()
    await db.refresh(feedback)
    audit("feedback_submitted", user_id=str(user.id), tenant_id=str(feedback.organization_id))
    return _feedback_response(feedback)


@router.get("/v1/feedback/mine", response_model=list[FeedbackResponse])
async def list_my_feedback(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=1_000_000),
    principal: Principal = Depends(authorized_principal_dep),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    result = await db.execute(
        select(Feedback)
        .where(
            Feedback.organization_id == UUID(principal.tenant_id),
            Feedback.user_id == principal_uuid(principal),
        )
        .order_by(Feedback.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return [_feedback_response(item) for item in result.scalars().all()]


@router.get("/v1/admin/feedback", response_model=list[FeedbackAdminResponse])
async def list_feedback_for_platform_admin(
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0, le=1_000_000),
    auth: tuple[Principal, AsyncSession, User] = Depends(system_admin_dep),
):
    _, db, _ = auth
    query = (
        select(Feedback, Organization.name)
        .join(Organization, Organization.id == Feedback.organization_id)
        .order_by(Feedback.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if status:
        query = query.where(Feedback.status == status)
    if category:
        query = query.where(Feedback.category == category)
    result = await db.execute(query)
    return [_admin_feedback_response(item, name) for item, name in result.all()]


@router.patch("/v1/admin/feedback/{feedback_id}", response_model=FeedbackAdminResponse)
async def update_feedback_for_platform_admin(
    feedback_id: UUID,
    payload: UpdateFeedbackRequest,
    auth: tuple[Principal, AsyncSession, User] = Depends(system_admin_dep),
):
    _, db, system_admin = auth
    result = await db.execute(
        select(Feedback, Organization.name)
        .join(Organization, Organization.id == Feedback.organization_id)
        .where(Feedback.id == feedback_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(404, "Feedback not found")
    feedback, organization_name = row
    feedback.status = payload.status
    feedback.priority = payload.priority
    feedback.admin_note = payload.admin_note
    feedback.updated_at = utc_now()
    db.add(
        AuditEvent(
            organization_id=feedback.organization_id,
            user_id=system_admin.id,
            event_type="feedback_updated",
            event_metadata={
                "feedback_id": str(feedback.id),
                "status": feedback.status,
                "priority": feedback.priority,
            },
        )
    )
    await db.commit()
    await db.refresh(feedback)
    audit(
        "feedback_updated",
        user_id=str(system_admin.id),
        feedback_id=str(feedback.id),
        status=feedback.status,
    )
    return _admin_feedback_response(feedback, organization_name)
