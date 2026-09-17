"""Authentication and refresh-session routes."""

import hashlib
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import auth_ready
from app.audit import audit
from app.config import settings
from app.core.runtime import limiter
from app.db import get_db
from app.db_models import Membership, Organization, RefreshSession, User
from app.models import (
    AcceptInviteRequest,
    AuthResponse,
    LoginRequest,
)
from app.services.auth_service import (
    accept_invitation,
    access_token,
    active_membership,
    authenticate,
    build_auth_response,
    issue_refresh_session,
)

router = APIRouter(tags=["auth"])


async def build_auth_response_for_session(
    db: AsyncSession, user: User, organization: Organization, membership: Membership
) -> AuthResponse:
    user_data, current_org, organizations = await build_auth_response(
        db, user, organization, membership
    )
    return AuthResponse(
        access_token=access_token(user, organization, membership),
        expires_in=settings.access_token_minutes * 60,
        user=user_data,
        current_organization=current_org,
        organizations=organizations,
    )


def attach_refresh_cookie(response: JSONResponse, refresh_token: str) -> JSONResponse:
    response.set_cookie(
        "refresh_token",
        refresh_token,
        max_age=settings.refresh_token_days * 86400,
        httponly=True,
        secure=settings.environment != "development",
        # Netlify and the API commonly use different sites in production.
        # Lax cookies are not sent with cross-site fetch requests, which
        # would make the short-lived access token impossible to refresh.
        samesite="none" if settings.environment == "production" else "lax",
        # Organization switching also rotates the refresh session, so the
        # cookie must be sent to that /v1 endpoint as well as /auth.
        path="/",
    )
    return response


def validate_cookie_request_origin(request: Request) -> None:
    """Require a browser request origin trusted by this deployment."""
    origin = request.headers.get("origin")
    if not origin:
        raise HTTPException(403, "Request origin is required")
    configured_origins = {
        value.strip() for value in settings.cors_allowed_origins.split(",") if value.strip()
    }
    same_origin = f"{request.url.scheme}://{request.url.netloc}"
    if origin not in configured_origins and origin != same_origin:
        raise HTTPException(403, "Request origin is not allowed")


@router.post("/auth/login", response_model=AuthResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    auth_ready()
    try:
        user, organization, membership = await authenticate(db, payload.email, payload.password)
    except ValueError as exc:
        audit("login_failed", email=payload.email, error=type(exc).__name__)
        raise HTTPException(401, str(exc)) from exc
    refresh_token = await issue_refresh_session(db, user, organization.id)
    await db.commit()
    response = JSONResponse(
        (await build_auth_response_for_session(db, user, organization, membership)).model_dump(
            mode="json"
        )
    )
    audit("login_succeeded", user_id=str(user.id), tenant_id=str(organization.id))
    return attach_refresh_cookie(response, refresh_token)


@router.post("/auth/accept-invite", response_model=AuthResponse)
@limiter.limit("5/minute")
async def accept_invite(
    request: Request,
    payload: AcceptInviteRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    auth_ready()
    try:
        user, organization, membership = await accept_invitation(
            db, payload.invitation_token, payload.password
        )
        refresh_token = await issue_refresh_session(db, user, organization.id)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        audit("invite_accept_failed", error=type(exc).__name__)
        raise HTTPException(400, str(exc)) from exc
    except IntegrityError as exc:
        await db.rollback()
        audit("invite_accept_failed", error=type(exc).__name__)
        raise HTTPException(409, "Invitation could not be accepted") from exc
    response = JSONResponse(
        (await build_auth_response_for_session(db, user, organization, membership)).model_dump(
            mode="json"
        )
    )
    audit("invite_accepted", user_id=str(user.id), tenant_id=str(organization.id))
    return attach_refresh_cookie(response, refresh_token)


@router.post("/auth/refresh", response_model=AuthResponse)
@limiter.limit("20/minute")
async def refresh(request: Request, db: AsyncSession = Depends(get_db)):  # noqa: B008
    auth_ready()
    validate_cookie_request_origin(request)
    raw_token = request.cookies.get("refresh_token")
    if not raw_token:
        raise HTTPException(401, "Refresh session required")
    result = await db.execute(
        select(RefreshSession, User)
        .join(User, User.id == RefreshSession.user_id)
        .where(RefreshSession.token_hash == hashlib.sha256(raw_token.encode()).hexdigest())
        .with_for_update()
    )
    row = result.first()
    now = datetime.now(UTC)
    if not row or row[0].expires_at <= now or not row[1].is_active:
        raise HTTPException(401, "Refresh session expired")
    old_session, user = row
    if old_session.revoked_at:
        await db.execute(
            RefreshSession.__table__.update()
            .where(RefreshSession.user_id == user.id)
            .values(revoked_at=now)
        )
        await db.commit()
        audit(
            "refresh_reuse_detected",
            user_id=str(user.id),
            tenant_id=str(old_session.organization_id),
        )
        raise HTTPException(401, "Refresh session expired")
    old_session.revoked_at = now
    try:
        organization, membership = await active_membership(db, user.id, old_session.organization_id)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(403, "Organization membership is no longer active") from exc
    new_refresh = await issue_refresh_session(db, user, organization.id)
    await db.commit()
    audit("refresh_succeeded", user_id=str(user.id), tenant_id=str(organization.id))
    response = JSONResponse(
        (await build_auth_response_for_session(db, user, organization, membership)).model_dump(
            mode="json"
        )
    )
    return attach_refresh_cookie(response, new_refresh)


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, db: AsyncSession = Depends(get_db)):  # noqa: B008
    validate_cookie_request_origin(request)
    raw_token = request.cookies.get("refresh_token")
    if raw_token:
        result = await db.execute(
            select(RefreshSession).where(
                RefreshSession.token_hash == hashlib.sha256(raw_token.encode()).hexdigest()
            )
        )
        session = result.scalar_one_or_none()
        if session:
            session.revoked_at = datetime.now(UTC)
            await db.commit()
            audit("logout_succeeded", user_id=str(session.user_id))
    response = JSONResponse(status_code=204, content=None)
    response.delete_cookie("refresh_token", path="/")
    return response
