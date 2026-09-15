"""Tenant and user-scoped conversation history routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import authorized_principal_dep, principal_uuid
from app.db import get_db
from app.db_models import ChatMessage, Conversation
from app.models import ChatMessageResponse, ConversationSummary, Principal

router = APIRouter(prefix="/v1/conversations", tags=["conversations"])


@router.post("", response_model=ConversationSummary)
async def create_conversation(
    principal: Principal = Depends(authorized_principal_dep),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    conversation = Conversation(
        organization_id=UUID(principal.tenant_id), user_id=principal_uuid(principal)
    )
    db.add(conversation)
    await db.commit()
    return conversation


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0, le=1_000_000),
    principal: Principal = Depends(authorized_principal_dep),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.organization_id == UUID(principal.tenant_id),
            Conversation.user_id == principal_uuid(principal),
        )
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{conversation_id}/messages", response_model=list[ChatMessageResponse])
async def list_messages(
    conversation_id: UUID,
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0, le=1_000_000),
    principal: Principal = Depends(authorized_principal_dep),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    conversation = await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.organization_id == UUID(principal.tenant_id),
            Conversation.user_id == principal_uuid(principal),
        )
    )
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at)
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()
