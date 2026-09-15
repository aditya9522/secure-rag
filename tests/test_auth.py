import jwt
import pytest
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.admin import _organization_creation_conflict
from app.api.auth import attach_refresh_cookie
from app.config import Settings, settings
from app.models import InviteMemberRequest, UpdateMemberRequest, UpdateProfileRequest
from app.security.auth import decode_principal


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


def test_organization_creation_does_not_return_database_error_details():
    error = IntegrityError("INSERT secret_schema", {"owner_password": "sensitive"}, Exception())

    response_error = _organization_creation_conflict(error)

    assert response_error.status_code == 409
    assert response_error.detail == "Organization could not be created"
    assert "secret_schema" not in response_error.detail
