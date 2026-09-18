"""Authenticated RAG query routes, including streamed responses."""

import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import authorized_principal_dep
from app.audit import audit
from app.config import settings
from app.core import runtime
from app.db import get_db
from app.db_models import DocumentRecord, DocumentStatus
from app.models import Principal, QueryRequest, QueryResponse
from app.rag import answer_query
from app.services.chat_service import persist_query

router = APIRouter(prefix="/v1/query", tags=["query"])


async def active_document_ids(db: AsyncSession, principal: Principal) -> dict[str, int]:
    rows = await db.execute(
        select(DocumentRecord.id, DocumentRecord.version).where(
            DocumentRecord.organization_id == UUID(principal.tenant_id),
            DocumentRecord.status == DocumentStatus.active.value,
        )
    )
    return {str(document_id): int(version) for document_id, version in rows}


async def run_answer(
    body: QueryRequest,
    principal: Principal,
    db: AsyncSession,
    on_delta=None,
) -> QueryResponse:
    if runtime.openai_provider is None or runtime.pinecone_provider is None:
        raise HTTPException(503, "Providers are not configured")
    if len(body.query) > settings.max_query_chars:
        raise HTTPException(422, "Query is too long")
    return await runtime.run_provider_operation(
        answer_query,
        principal,
        body.query,
        runtime.openai_provider,
        runtime.pinecone_provider,
        await active_document_ids(db, principal),
        on_delta=on_delta,
    )


@router.post("", response_model=QueryResponse)
@runtime.limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def query(
    request: Request,
    body: QueryRequest,
    principal: Principal = Depends(authorized_principal_dep),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    try:
        result = await run_answer(body, principal, db)
    except HTTPException:
        raise
    except RuntimeError as exc:
        audit(
            "rag_provider_failure",
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            error=type(exc).__name__,
        )
        raise HTTPException(503, "RAG service is temporarily unavailable") from exc
    except Exception as exc:
        audit(
            "rag_unexpected_failure",
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            error=type(exc).__name__,
        )
        raise HTTPException(503, "RAG service is temporarily unavailable") from exc
    audit_query(principal, result)
    try:
        conversation_id = await persist_query(db, principal, body, result)
    except HTTPException:
        await db.rollback()
        raise
    except (ValueError, IntegrityError) as exc:
        await db.rollback()
        logging.getLogger(__name__).error("query_persistence_failed type=%s", type(exc).__name__)
        raise HTTPException(503, "Query history is temporarily unavailable") from exc
    return result.model_copy(update={"conversation_id": conversation_id})


def audit_query(principal: Principal, result: QueryResponse) -> None:
    audit(
        "rag_query",
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
        grounded=result.grounded,
        refused=result.refused,
        flags=result.policy_flags,
    )


def sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


@router.post("/stream")
@runtime.limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def query_stream(
    request: Request,
    body: QueryRequest,
    principal: Principal = Depends(authorized_principal_dep),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    if runtime.openai_provider is None or runtime.pinecone_provider is None:
        raise HTTPException(503, "Providers are not configured")
    if len(body.query) > settings.max_query_chars:
        raise HTTPException(422, "Query is too long")
    document_ids = await active_document_ids(db, principal)

    async def event_stream():
        result_holder: list[QueryResponse] = []
        error_holder: list[Exception] = []
        generation_done = asyncio.Event()

        async def generate() -> None:
            try:
                # Keep provider deltas internal until the complete answer has
                # passed moderation, citation, and grounding validation. The
                # validated answer is streamed below as UI-friendly chunks.
                result_holder.append(
                    await runtime.run_provider_operation(
                        answer_query,
                        principal,
                        body.query,
                        runtime.openai_provider,
                        runtime.pinecone_provider,
                        document_ids,
                        on_delta=lambda _delta: None,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - convert provider failures to safe SSE
                error_holder.append(exc)
            finally:
                generation_done.set()

        task = asyncio.create_task(generate())
        try:
            yield sse("status", {"status": "started"})
            while not generation_done.is_set():
                if await request.is_disconnected():
                    return
                try:
                    await asyncio.wait_for(generation_done.wait(), timeout=0.5)
                except TimeoutError:
                    continue
            await task

            if error_holder:
                error = error_holder[0]
                audit(
                    "rag_stream_failed",
                    user_id=principal.user_id,
                    tenant_id=principal.tenant_id,
                    error=type(error).__name__,
                )
                yield sse("error", {"detail": "RAG service is temporarily unavailable"})
                return

            result = result_holder[0]
            audit_query(principal, result)
            try:
                conversation_id = await persist_query(db, principal, body, result)
            except HTTPException as exc:
                await db.rollback()
                yield sse("error", {"detail": exc.detail})
                return
            except (ValueError, IntegrityError) as exc:
                await db.rollback()
                logging.getLogger(__name__).error(
                    "query_stream_persistence_failed type=%s", type(exc).__name__
                )
                yield sse("error", {"detail": "Query history is temporarily unavailable"})
                return

            response = result.model_copy(update={"conversation_id": conversation_id})
            for start in range(0, len(response.answer), 320):
                if await request.is_disconnected():
                    return
                yield sse("delta", {"content": response.answer[start : start + 320]})
                await asyncio.sleep(0)
            yield sse("complete", {"response": response.model_dump(mode="json")})
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
