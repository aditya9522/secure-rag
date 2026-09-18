"""Application composition, middleware, and router registration."""

import logging
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request

from app.api import (
    admin,
    auth,
    conversations,
    documents,
    feedback,
    health,
    organizations,
    profile,
    query,
)
from app.audit import request_id_context, set_request_id
from app.config import settings
from app.core import runtime
from app.db import close_database

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

app = FastAPI(
    title="Secure RAG — OpenAI + Pinecone",
    version="1.0.0",
    docs_url=None if settings.environment == "production" else "/docs",
    redoc_url=None if settings.environment == "production" else "/redoc",
    openapi_url=None if settings.environment == "production" else "/openapi.json",
)
app.state.limiter = runtime.limiter


@app.middleware("http")
async def security_headers(request: Request, call_next):
    incoming_request_id = request.headers.get("X-Request-ID", "").strip()
    request_id = (
        incoming_request_id[:128]
        if incoming_request_id
        and all(ord(char) >= 32 and ord(char) != 127 for char in incoming_request_id)
        else uuid4().hex
    )
    request.state.request_id = request_id
    token = set_request_id(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.url.path.startswith(("/auth/", "/v1/")):
            response.headers["Cache-Control"] = "no-store"
        return response
    finally:
        request_id_context.reset(token)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return await exc.handler(request, exc)


@app.on_event("shutdown")
async def shutdown_database():
    await close_database()


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(organizations.router)
app.include_router(documents.router)
app.include_router(conversations.router)
app.include_router(query.router)
app.include_router(admin.router)
app.include_router(feedback.router)

# Wrap the complete application so CORS headers are also present on unhandled
# error responses. This keeps browser diagnostics actionable while the server
# logs retain the actual exception details.
if settings.cors_allowed_origins:
    app = CORSMiddleware(
        app,
        allow_origins=[
            origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
    )
