"""Chat routing and message orchestration."""
from typing import Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import APIRouter, Depends, HTTPException, status
import uuid
import structlog

from ..dependencies import get_db, get_cache
from ..models.database import Conversation, Message, ToolRun, Citation
from ..schemas.common import (
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationResponse,
    MessageResponse,
    PaginatedResponse,
    CitationResponse,
    ToolRunResponse,
)
from ..services.audit import AuditService
from ..services.cache import CacheService

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    cache: Optional[CacheService] = Depends(get_cache),
) -> ChatResponse:
    """
    Send a chat message and get AI response with tool executions.

    Args:
        request: Chat request with message and optional conversation_id
        db: Database session
        cache: Cache service

    Returns:
        Chat response with message, tool runs, and citations
    """
    try:
        # Get or create conversation
        if request.conversation_id:
            result = await db.execute(
                select(Conversation).where(Conversation.id == request.conversation_id)
            )
            conversation = result.scalars().first()
            if not conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found",
                )
        else:
            conversation = Conversation(
                id=uuid.uuid4(),
                user_id=None,  # TODO: Get from auth context
                title=request.message[:100],
            )
            db.add(conversation)
            await db.flush()

        # Store user message
        user_message = Message(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role="user",
            content=request.message,
        )
        db.add(user_message)
        await db.flush()

        # TODO: Call LLM with message and tools
        # This is a placeholder; real implementation would:
        # 1. Call Claude/OpenAI with tool specs
        # 2. Execute tools as directed
        # 3. Build response with citations
        assistant_response = "Processing message..."
        tool_runs_data = []
        all_citations = []

        # Store assistant message
        assistant_message = Message(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_response,
        )
        db.add(assistant_message)
        await db.flush()

        # Log audit event
        audit_service = AuditService()
        await audit_service.log_event(
            db=db,
            event_type="create",
            entity_type="message",
            entity_id=str(assistant_message.id),
            details={"role": "assistant", "content_length": len(assistant_response)},
            actor_id=None,
        )

        await db.commit()

        # Convert citations to response format
        citation_responses = [
            CitationResponse(
                source_name=c.source_name,
                source_url=c.source_url,
                source_label=c.source_label,
                retrieved_at=c.retrieved_at,
                snippet=c.snippet,
            )
            for c in all_citations
        ]

        # Convert tool runs
        tool_run_responses = [
            ToolRunResponse(
                tool_id=tr["tool_id"],
                input_params=tr["input_params"],
                output=tr["output"],
                citations=[
                    CitationResponse(
                        source_name=c["source_name"],
                        source_url=c["source_url"],
                        source_label=c["source_label"],
                        retrieved_at=datetime.fromisoformat(c["retrieved_at"]),
                        snippet=c.get("snippet"),
                    )
                    for c in tr.get("citations", [])
                ],
                duration_ms=tr["duration_ms"],
                status=tr["status"],
                error_message=tr.get("error_message"),
            )
            for tr in tool_runs_data
        ]

        return ChatResponse(
            conversation_id=conversation.id,
            message_id=assistant_message.id,
            message=assistant_response,
            tool_runs=tool_run_responses,
            citations=citation_responses,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("chat_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process message",
        )


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    request: ConversationCreate,
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """
    Create a new conversation.

    Args:
        request: Conversation creation request
        db: Database session

    Returns:
        Created conversation
    """
    try:
        conversation = Conversation(
            id=uuid.uuid4(),
            user_id=None,  # TODO: Get from auth context
            title=request.title,
        )
        db.add(conversation)
        await db.commit()

        logger.info("conversation_created", conversation_id=str(conversation.id))

        return ConversationResponse(
            id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )
    except Exception as e:
        logger.error("conversation_creation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create conversation",
        )


@router.get("/conversations", response_model=PaginatedResponse[ConversationResponse])
async def list_conversations(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ConversationResponse]:
    """
    List user's conversations.

    Args:
        skip: Pagination offset
        limit: Results per page
        db: Database session

    Returns:
        Paginated list of conversations
    """
    try:
        # TODO: Filter by authenticated user
        result = await db.execute(
            select(Conversation).order_by(Conversation.updated_at.desc()).offset(skip).limit(limit)
        )
        conversations = result.scalars().all()

        count_result = await db.execute(select(Conversation))
        total = len(count_result.scalars().all())

        items = [
            ConversationResponse(
                id=c.id,
                title=c.title,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in conversations
        ]

        pages = (total + limit - 1) // limit
        return PaginatedResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
            pages=pages,
        )
    except Exception as e:
        logger.error("list_conversations_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list conversations",
        )


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """
    Get conversation details.

    Args:
        conversation_id: Conversation ID
        db: Database session

    Returns:
        Conversation details
    """
    try:
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalars().first()

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

        return ConversationResponse(
            id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_conversation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get conversation",
        )


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=PaginatedResponse[MessageResponse],
)
async def get_conversation_messages(
    conversation_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[MessageResponse]:
    """
    Get paginated messages from conversation.

    Args:
        conversation_id: Conversation ID
        skip: Pagination offset
        limit: Results per page
        db: Database session

    Returns:
        Paginated messages
    """
    try:
        # Verify conversation exists
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        if not result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

        # Get messages
        query = select(Message).where(Message.conversation_id == conversation_id)
        count_result = await db.execute(query)
        total = len(count_result.scalars().all())

        result = await db.execute(
            query.order_by(Message.created_at).offset(skip).limit(limit)
        )
        messages = result.scalars().all()

        items = [
            MessageResponse(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
            )
            for m in messages
        ]

        pages = (total + limit - 1) // limit
        return PaginatedResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
            pages=pages,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_messages_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get messages",
        )
