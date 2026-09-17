import asyncio
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request

from app.api.admin import _organization_creation_conflict
from app.api.auth import attach_refresh_cookie, validate_cookie_request_origin
from app.api.organizations import _assert_can_grant_role, invite_member
from app.config import Settings, settings
from app.models import InviteMemberRequest, UpdateMemberRequest, UpdateProfileRequest
from app.security.auth import decode_principal
from app.services.auth_service import access_token


def test_default_jwt_secret_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", "replace-me")

    with pytest.raises(Exception) as exc_info:
        decode_principal("not-used")

    assert getattr(exc_info.value, "status_code", None) == 503


def test_production_settings_reject_default_security_configuration():
    with pytest.raises(ValueError):
        Settings(_env_file=None, environment="production")


def test_jwt_without_expiration_is_rejected(monkeypatch):
    secret = "a" * 40
    monkeypatch.setattr(settings, "jwt_secret", secret)
    token = jwt.encode(
        {
            "sub": "u1",
            "tenant_id": "tenant-a",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": 1,
        },
        secret,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(Exception) as exc_info:
        decode_principal(token)

    assert getattr(exc_info.value, "status_code", None) == 401


def test_local_dev_tokens_are_rejected_outside_development():
    with pytest.raises(ValueError):
        Settings(_env_file=None, environment="staging", allow_local_dev_tokens=True)


def test_production_database_placeholder_is_rejected():
    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings(
            _env_file=None,
            environment="production",
            jwt_secret="a" * 40,
            database_url="postgresql+asyncpg://secure_rag:CHANGE_ME@localhost:5432/secure_rag",
            rate_limit_storage_uri="redis://localhost:6379/0",
        )


def test_profile_update_requires_a_real_change_and_complete_password_pair():
    with pytest.raises(ValueError):
        UpdateProfileRequest()
    with pytest.raises(ValueError):
        UpdateProfileRequest(new_password="a" * 12)
    assert UpdateProfileRequest(full_name="Updated User")


def test_profile_and_membership_names_reject_whitespace_only_values():
    with pytest.raises(ValueError):
        UpdateProfileRequest(full_name="  ")
    with pytest.raises(ValueError):
        InviteMemberRequest(email="user@example.com", full_name="  ")


def test_membership_group_inputs_are_normalized_and_validated():
    request = UpdateMemberRequest(role="member", groups=[" engineering ", "engineering"])
    assert request.groups == ["engineering"]
    with pytest.raises(ValueError):
        UpdateMemberRequest(role="member", groups=["\n"])


def test_production_requires_pinecone_deletion_protection():
    with pytest.raises(ValueError, match="PINECONE_DELETION_PROTECTION"):
        Settings(
            _env_file=None,
            environment="production",
            jwt_secret="a" * 40,
            database_url="postgresql+asyncpg://secure_rag:real-secret@localhost:5432/secure_rag",
            rate_limit_storage_uri="redis://localhost:6379/0",
            pinecone_deletion_protection="disabled",
        )


def test_refresh_cookie_is_available_to_organization_switch_and_logout():
    response = attach_refresh_cookie(JSONResponse({}), "refresh-token")
    cookie = response.headers["set-cookie"]
    assert "Path=/" in cookie

    response = JSONResponse(status_code=204, content=None)
    response.delete_cookie("refresh_token", path="/")
    assert 'refresh_token=""' in response.headers["set-cookie"]
    assert "Path=/" in response.headers["set-cookie"]


def test_production_refresh_cookie_supports_cross_site_frontend(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")

    response = attach_refresh_cookie(JSONResponse({}), "refresh-token")
    cookie = response.headers["set-cookie"]

    assert "SameSite=none" in cookie
    assert "Secure" in cookie


def _request_with_origin(origin: str | None) -> Request:
    headers = [] if origin is None else [(b"origin", origin.encode())]
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "https",
            "path": "/auth/logout",
            "raw_path": b"/auth/logout",
            "query_string": b"",
            "headers": headers,
            "server": ("api.example.com", 443),
            "client": ("127.0.0.1", 1234),
        }
    )


def test_cookie_request_origin_accepts_configured_frontend(monkeypatch):
    monkeypatch.setattr(settings, "cors_allowed_origins", "https://app.example.com")

    validate_cookie_request_origin(_request_with_origin("https://app.example.com"))


def test_cookie_request_origin_rejects_missing_or_untrusted_origin(monkeypatch):
    monkeypatch.setattr(settings, "cors_allowed_origins", "https://app.example.com")

    with pytest.raises(Exception) as missing:
        validate_cookie_request_origin(_request_with_origin(None))
    assert getattr(missing.value, "status_code", None) == 403

    with pytest.raises(Exception) as untrusted:
        validate_cookie_request_origin(_request_with_origin("https://attacker.example"))
    assert getattr(untrusted.value, "status_code", None) == 403


def test_authentication_cannot_be_disabled_with_an_unauthorized_fallback():
    with pytest.raises(ValueError, match="REQUIRE_AUTH=false is unsupported"):
        Settings(_env_file=None, require_auth=False)


def test_only_organization_owners_can_grant_administrator_access():
    _assert_can_grant_role("owner", "admin")
    _assert_can_grant_role("admin", "member")

    with pytest.raises(Exception) as exc_info:
        _assert_can_grant_role("admin", "admin")
    assert getattr(exc_info.value, "status_code", None) == 403


def test_invitation_route_rejects_admin_grant_from_non_owner():
    payload = InviteMemberRequest(
        email="member@example.com",
        full_name="Member User",
        role="admin",
    )

    with pytest.raises(Exception) as exc_info:
        asyncio.run(
            invite_member(
                payload,
                (SimpleNamespace(tenant_id=str(uuid4())), None, SimpleNamespace(role="admin")),
            )
        )
    assert getattr(exc_info.value, "status_code", None) == 403


def test_system_admin_member_does_not_receive_tenant_admin_claim(monkeypatch):
    secret = "a" * 40
    monkeypatch.setattr(settings, "jwt_secret", secret)
    user = SimpleNamespace(id=uuid4(), is_system_admin=True)
    organization = SimpleNamespace(id=uuid4())
    membership = SimpleNamespace(role="member", groups=[], classification_max="internal")

    principal = decode_principal(access_token(user, organization, membership))

    assert principal.can_manage_access is False


def test_organization_creation_does_not_return_database_error_details():
    error = IntegrityError("INSERT secret_schema", {"owner_password": "sensitive"}, Exception())

    response_error = _organization_creation_conflict(error)

    assert response_error.status_code == 409
    assert response_error.detail == "Organization could not be created"
    assert "secret_schema" not in response_error.detail
