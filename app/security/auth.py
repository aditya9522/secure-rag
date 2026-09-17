import jwt
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.audit import audit
from app.config import settings
from app.models import Classification, Principal

bearer = HTTPBearer(auto_error=False)


def decode_principal(token: str) -> Principal:
    if settings.require_auth and not settings.jwt_secret_configured:
        raise HTTPException(status_code=503, detail="Authentication is not configured")
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub", "tenant_id"]},
        )
    except jwt.PyJWTError as exc:
        audit("authentication_failed", reason="invalid_token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc
    try:
        user_id = payload["sub"]
        tenant_id = payload["tenant_id"]
        groups = payload.get("groups", [])
        can_manage_access = payload.get("can_manage_access", False)
        if (
            not isinstance(user_id, str)
            or not isinstance(tenant_id, str)
            or not isinstance(groups, list)
            or not isinstance(can_manage_access, bool)
        ):
            raise TypeError("Identity claims have invalid types")
        return Principal(
            user_id=user_id,
            tenant_id=tenant_id,
            groups=groups,
            classification_max=Classification(payload.get("classification_max", "internal")),
            can_manage_access=can_manage_access,
        )
    except (KeyError, ValueError, TypeError) as exc:
        audit("authentication_failed", reason="invalid_claims")
        raise HTTPException(status_code=401, detail="Invalid authorization claims") from exc


def get_principal(credentials: HTTPAuthorizationCredentials | None) -> Principal:
    if not credentials:
        audit("authentication_failed", reason="missing_bearer")
        raise HTTPException(status_code=401, detail="Bearer token required")
    return decode_principal(credentials.credentials)
