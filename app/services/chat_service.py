"""Conversation persistence services."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models import AuditEvent, ChatMessage, Conversation
from app.models import Principal, QueryRequest, QueryResponse
from app.security.policy import inspect_text


async def persist_query(
    db: AsyncSession, principal: Principal, body: QueryRequest, result: QueryResponse
) -> UUID:
    organization_id = UUID(principal.tenant_id)
    user_id = UUID(principal.user_id)
    conversation = None
    if body.conversation_id:
        conversation = await db.scalar(
            select(Conversation).where(
                Conversation.id == body.conversation_id,
                Conversation.organization_id == organization_id,
                Conversation.user_id == user_id,
            )
        )
        if not conversation:
            raise HTTPException(404, "Conversation not found")
    else:
        conversation = Conversation(
            organization_id=organization_id,
            user_id=user_id,
            title=inspect_text(body.query).sanitized_text[:200],
        )
        db.add(conversation)
        await db.flush()

    safe_query = inspect_text(body.query).sanitized_text
    if conversation.title == "New conversation":
        conversation.title = safe_query[:200]
    db.add(
        ChatMessage(
            conversation_id=conversation.id,
            role="user",
            content=safe_query,
            mode=result.mode,
            citations=[],
        )
    )
    db.add(
        ChatMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=result.answer,
            mode=result.mode,
            citations=[citation.model_dump(mode="json") for citation in result.citations],
        )
    )
    conversation.updated_at = datetime.now(UTC)
    db.add(
        AuditEvent(
            organization_id=organization_id,
            user_id=user_id,
            event_type="rag_query",
            event_metadata={
                "grounded": result.grounded,
                "refused": result.refused,
                "mode": result.mode,
                "flags": result.policy_flags,
            },
        )
    )
    await db.commit()
    return conversation.id
