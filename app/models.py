from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class Classification(str, Enum):
    public = "public"
    internal = "internal"
    confidential = "confidential"
    restricted = "restricted"


CLASSIFICATION_RANK = {
    Classification.public: 0,
    Classification.internal: 1,
    Classification.confidential: 2,
    Classification.restricted: 3,
}


def _normalize_groups(values: list[str]) -> list[str]:
    normalized = []
    for value in values:
        value = value.strip()
        if (
            not value
            or len(value) > 128
            or any(ord(char) < 32 or ord(char) == 127 for char in value)
        ):
            raise ValueError(
                "Group names must be non-empty, bounded, and contain no control characters"
            )
        normalized.append(value)
    if len(normalized) > 50:
        raise ValueError("A principal cannot have more than 50 groups")
    return list(dict.fromkeys(normalized))


def _normalize_display_name(value: str) -> str:
    value = value.strip()
    if len(value) < 2:
        raise ValueError("Names must contain at least two non-whitespace characters")
    return value


class Principal(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    groups: list[str] = Field(default_factory=list)
    classification_max: Classification = Classification.internal
    can_manage_access: bool = False

    @field_validator("user_id", "tenant_id")
    @classmethod
    def validate_identity_value(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Identity values must be non-empty")
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("Identity values cannot contain control characters")
        return value

    @field_validator("groups")
    @classmethod
    def normalize_groups(cls, values: list[str]) -> list[str]:
        return _normalize_groups(values)

    def can_read_classification(self, classification: Classification) -> bool:
        return CLASSIFICATION_RANK[classification] <= CLASSIFICATION_RANK[self.classification_max]


class DevTokenRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    groups: list[str] = Field(default_factory=list, max_length=50)
    classification_max: Classification = Classification.internal
    can_manage_access: bool = False

    @field_validator("groups")
    @classmethod
    def normalize_group_values(cls, values: list[str]) -> list[str]:
        return _normalize_groups(values)


class CreateOrganizationRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    owner_email: str = Field(min_length=3, max_length=320)
    owner_full_name: str = Field(min_length=2, max_length=160)
    owner_password: str = Field(min_length=12, max_length=128)

    @field_validator("name", "owner_full_name")
    @classmethod
    def normalize_names(cls, value: str) -> str:
        return _normalize_display_name(value)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class UpdateProfileRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    current_password: str | None = Field(default=None, min_length=1, max_length=128)
    new_password: str | None = Field(default=None, min_length=12, max_length=128)

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str | None) -> str | None:
        return None if value is None else _normalize_display_name(value)

    @model_validator(mode="after")
    def validate_password_change(self) -> "UpdateProfileRequest":
        if (self.current_password is None) != (self.new_password is None):
            raise ValueError("Current and new password are both required to change password")
        if self.full_name is None and self.new_password is None:
            raise ValueError("At least one profile field must be updated")
        return self


class SwitchOrganizationRequest(BaseModel):
    organization_id: UUID


class AcceptInviteRequest(BaseModel):
    invitation_token: str = Field(min_length=32, max_length=128)
    password: str = Field(min_length=12, max_length=128)


class InvitationResponse(BaseModel):
    invitation_id: UUID
    invitation_token: str
    expires_at: datetime


class InviteMemberRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    full_name: str = Field(min_length=2, max_length=160)
    role: Literal["admin", "member"] = "member"
    groups: list[str] = Field(default_factory=list, max_length=50)
    classification_max: Classification = Classification.internal

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        return _normalize_display_name(value)

    @field_validator("groups")
    @classmethod
    def normalize_group_values(cls, values: list[str]) -> list[str]:
        return _normalize_groups(values)


class UpdateMemberRequest(BaseModel):
    role: Literal["admin", "member", "suspended"]
    groups: list[str] = Field(default_factory=list, max_length=50)
    classification_max: Classification = Classification.internal

    @field_validator("groups")
    @classmethod
    def normalize_group_values(cls, values: list[str]) -> list[str]:
        return _normalize_groups(values)


class OrganizationSummary(BaseModel):
    id: UUID
    name: str
    slug: str
    role: str
    groups: list[str] = Field(default_factory=list)
    classification_max: Classification


class UserSummary(BaseModel):
    id: UUID
    email: str
    full_name: str
    is_system_admin: bool


class OrganizationCreationResponse(BaseModel):
    organization: OrganizationSummary
    owner: UserSummary


class AuthResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserSummary
    current_organization: OrganizationSummary
    organizations: list[OrganizationSummary]


class MeResponse(BaseModel):
    user: UserSummary
    current_organization: OrganizationSummary
    organizations: list[OrganizationSummary]


class DocumentSummary(BaseModel):
    id: UUID
    title: str
    classification: Classification
    allowed_groups: list[str]
    source_uri: str | None
    status: str
    chunks_indexed: int
    created_at: datetime
    updated_at: datetime


class ConversationSummary(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ChatMessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    mode: Literal["grounded", "conversational", "refused"]
    citations: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class AuditEventResponse(BaseModel):
    id: UUID
    event_type: str
    metadata: dict[str, Any]
    user_id: UUID | None
    created_at: datetime


class NotificationResponse(BaseModel):
    id: UUID
    event_type: str
    title: str
    detail: str
    severity: Literal["info", "success", "warning"]
    created_at: datetime


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    conversation_id: UUID | None = None


class Citation(BaseModel):
    document_id: str
    document_title: str
    chunk_id: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    conversation_id: UUID | None = None
    grounded: bool
    refused: bool = False
    policy_flags: list[str] = Field(default_factory=list)
    mode: Literal["grounded", "conversational", "refused"] = "grounded"


class IngestResponse(BaseModel):
    document_id: str
    chunks_indexed: int
    classification: Classification
    source_uri: str | None = None
    provenance: dict[str, Any]
