import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db_models import (
    Invitation,
    Membership,
    MembershipStatus,
    Organization,
    OrganizationRole,
    RefreshSession,
    User,
)
from app.models import Classification, OrganizationSummary, UserSummary
from app.security.passwords import hash_password, verify_password


def normalize_email(email: str) -> str:
    return email.strip().lower()


def organization_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:70] or "workspace"


def _classification(value: str) -> Classification:
    try:
        return Classification(value)
    except ValueError:
        return Classification.internal


def user_summary(user: User) -> UserSummary:
    return UserSummary(
        id=user.id, email=user.email, full_name=user.full_name, is_system_admin=user.is_system_admin
    )


def organization_summary(org: Organization, membership: Membership) -> OrganizationSummary:
    return OrganizationSummary(
        id=org.id,
        name=org.name,
        slug=org.slug,
        role=membership.role,
        groups=membership.groups or [],
        classification_max=_classification(membership.classification_max),
    )


def access_token(user: User, org: Organization, membership: Membership) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user.id),
            "tenant_id": str(org.id),
            "groups": membership.groups or [],
            "classification_max": membership.classification_max,
            "can_manage_access": membership.role
            in {OrganizationRole.owner.value, OrganizationRole.admin.value},
            "role": membership.role,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": now,
            "exp": now + timedelta(minutes=settings.access_token_minutes),
            "jti": secrets.token_hex(16),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


async def issue_refresh_session(session: AsyncSession, user: User, organization_id: UUID) -> str:
    raw = secrets.token_urlsafe(48)
    session.add(
        RefreshSession(
            user_id=user.id,
            organization_id=organization_id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
        )
    )
    return raw


async def active_membership(
    session: AsyncSession, user_id: UUID, organization_id: UUID | None = None
) -> tuple[Organization, Membership]:
    query = (
        select(Organization, Membership)
        .join(Membership, Membership.organization_id == Organization.id)
        .where(Membership.user_id == user_id, Membership.status == MembershipStatus.active.value)
        .order_by(Membership.created_at)
    )
    if organization_id:
        query = query.where(Organization.id == organization_id)
    result = await session.execute(query)
    row = result.first()
    if not row:
        raise ValueError("No active organization membership found")
    return row


async def authenticate(
    session: AsyncSession, email: str, password: str
) -> tuple[User, Organization, Membership]:
    result = await session.execute(select(User).where(User.email == normalize_email(email)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        raise ValueError("Invalid email or password")
    org, membership = await active_membership(session, user.id)
    return user, org, membership


async def build_auth_response(
    session: AsyncSession, user: User, org: Organization, membership: Membership
):
    result = await session.execute(
        select(Organization, Membership)
        .join(Membership, Membership.organization_id == Organization.id)
        .where(Membership.user_id == user.id, Membership.status == MembershipStatus.active.value)
        .order_by(Membership.created_at)
    )
    organizations = [organization_summary(row[0], row[1]) for row in result.all()]
    return user_summary(user), organization_summary(org, membership), organizations


async def create_organization_with_owner(
    session: AsyncSession,
    creator_id: UUID,
    organization_name: str,
    owner_email: str,
    owner_full_name: str,
    owner_password: str,
) -> tuple[User, Organization, Membership]:
    normalized_name = organization_name.strip()
    normalized_email = normalize_email(owner_email)
    normalized_full_name = owner_full_name.strip()
    if not normalized_name or not normalized_full_name:
        raise ValueError("Organization name and owner name are required")
    if "@" not in normalized_email or len(normalized_email) < 3:
        raise ValueError("A valid owner email is required")
    existing = await session.execute(select(User.id).where(User.email == normalized_email))
    if existing.scalar_one_or_none():
        raise ValueError("An account with the owner email already exists")
    owner = User(
        email=normalized_email,
        full_name=normalized_full_name,
        password_hash=hash_password(owner_password),
    )
    session.add(owner)
    await session.flush()

    base_slug = organization_slug(normalized_name)
    slug = base_slug
    suffix = 1
    while (
        await session.execute(select(Organization.id).where(Organization.slug == slug))
    ).scalar_one_or_none():
        suffix += 1
        slug = f"{base_slug}-{suffix}"
    organization = Organization(name=normalized_name, slug=slug, created_by=creator_id)
    session.add(organization)
    await session.flush()
    membership = Membership(
        user_id=owner.id,
        organization_id=organization.id,
        role=OrganizationRole.owner.value,
        status=MembershipStatus.active.value,
        groups=["owners"],
        classification_max=Classification.restricted.value,
    )
    session.add(membership)
    await session.flush()
    return owner, organization, membership


async def create_invitation(
    session: AsyncSession,
    organization_id: UUID,
    email: str,
    full_name: str,
    role: str,
    groups: list[str],
    classification_max: Classification,
) -> tuple[Invitation, str]:
    raw_token = secrets.token_urlsafe(48)
    invitation = Invitation(
        organization_id=organization_id,
        email=normalize_email(email),
        full_name=full_name.strip(),
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        role=role,
        groups=sorted(set(groups)),
        classification_max=classification_max.value,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    session.add(invitation)
    await session.flush()
    return invitation, raw_token


async def accept_invitation(
    session: AsyncSession, invitation_token: str, password: str
) -> tuple[User, Organization, Membership]:
    token_hash = hashlib.sha256(invitation_token.encode()).hexdigest()
    result = await session.execute(
        select(Invitation, Organization)
        .join(Organization, Organization.id == Invitation.organization_id)
        .where(
            Invitation.token_hash == token_hash,
            Invitation.accepted_at.is_(None),
            Invitation.expires_at > datetime.now(UTC),
        )
        .with_for_update()
    )
    row = result.first()
    if not row:
        raise ValueError("Invitation is invalid or expired")
    invitation, organization = row
    user_result = await session.execute(select(User).where(User.email == invitation.email))
    user = user_result.scalar_one_or_none()
    if not user:
        user = User(
            email=invitation.email,
            full_name=invitation.full_name,
            password_hash=hash_password(password),
        )
        session.add(user)
        await session.flush()
    elif not user.is_active:
        raise ValueError("This account is inactive")
    existing = await session.execute(
        select(Membership.id).where(
            Membership.user_id == user.id, Membership.organization_id == organization.id
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("This account is already a member of the organization")
    membership = Membership(
        user_id=user.id,
        organization_id=organization.id,
        role=invitation.role,
        status=MembershipStatus.active.value,
        groups=invitation.groups or [],
        classification_max=invitation.classification_max,
    )
    session.add(membership)
    invitation.accepted_at = datetime.now(UTC)
    await session.flush()
    return user, organization, membership
