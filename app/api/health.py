"""Liveness, readiness, and local-only development authentication routes."""

import logging
import time

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import auth_ready
from app.audit import audit
from app.config import settings
from app.core import runtime
from app.db import get_db
from app.models import DevTokenRequest
from app.services.document_service import (
    reconcile_expired_ingestion_jobs,
    reconcile_stale_documents,
)

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz():
    return {"status": "ok", "timestamp": int(time.time())}


@router.get("/readyz")
async def readyz(db: AsyncSession = Depends(get_db)):  # noqa: B008
    if runtime.openai_provider is None or runtime.pinecone_provider is None:
        raise HTTPException(status_code=503, detail="Providers are not configured")
    if settings.require_auth and not settings.jwt_secret_configured:
        raise HTTPException(status_code=503, detail="Authentication is not configured")
    try:
        await db.scalar(select(1))
        runtime.openai_provider.check_ready()
        runtime.pinecone_provider.check_ready()
        await reconcile_expired_ingestion_jobs(db)
        stale_documents = await reconcile_stale_documents(db)
        for tenant_id, document_id in stale_documents:
            try:
                await runtime.run_provider_operation(
                    runtime.pinecone_provider.delete_document, tenant_id, document_id
                )
            except Exception as cleanup_exc:  # noqa: BLE001 - stale data is already fail-closed
                logging.getLogger(__name__).error(
                    "stale_document_cleanup_failed tenant_id=%s document_id=%s type=%s",
                    tenant_id,
                    document_id,
                    type(cleanup_exc).__name__,
                )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Dependencies are not ready") from exc
    return {"status": "ready", "timestamp": int(time.time())}


@router.post("/auth/dev-token")
@runtime.limiter.limit("10/minute")
def dev_token(request: Request, payload: DevTokenRequest):
    if not settings.allow_local_dev_tokens or settings.environment != "development":
        raise HTTPException(404, "Not found")
    if request.client is None or request.client.host not in {"127.0.0.1", "::1"}:
        raise HTTPException(404, "Not found")
    auth_ready()
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": payload.user_id,
            "tenant_id": payload.tenant_id,
            "groups": payload.groups,
            "classification_max": payload.classification_max.value,
            "can_manage_access": payload.can_manage_access,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": now,
            "exp": now + 3600,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    audit("dev_token_issued", user_id=payload.user_id, tenant_id=payload.tenant_id)
    return {"access_token": token, "token_type": "bearer", "expires_in": 3600}
