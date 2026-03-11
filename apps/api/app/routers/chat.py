"""Chat routing and message orchestration."""
from typing import Optional, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import uuid
import asyncio
import structlog
import anthropic

from ..config import settings
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

ACQUISITION_SYSTEM_PROMPT = (
    "You are an expert federal acquisition assistant specializing in FAR/DFARS, "
    "IGCE methodology, market research, and contracting best practices. "
    "Answer questions clearly and cite relevant regulations when applicable."
)


# ── Schemas for the /send and /history endpoints ──────────────────────────────

class SendRequest(BaseModel):
    conversationId: str
    message: str
    context: Optional[dict] = None


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    timestamp: str


class SendResponse(BaseModel):
    conversationId: str
    messageId: str
    content: str
    toolRuns: list[Any] = []
    citations: list[Any] = []


@router.post("/send", response_model=SendResponse)
async def chat_send(
    request: SendRequest,
    db: AsyncSession = Depends(get_db),
) -> SendResponse:
    """
    Send a message and get a real Anthropic AI response.
    Accepts the shape the frontend posts: {conversationId, message, context}.
    Returns {conversationId, messageId, content, toolRuns, citations}.
    """
    try:
        # ── 1. Find or create conversation ────────────────────────────────────
        conv_id_str = request.conversationId
        try:
            conv_uuid = uuid.UUID(conv_id_str)
        except ValueError:
            conv_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, conv_id_str)

        result = await db.execute(
            select(Conversation).where(Conversation.id == conv_uuid)
        )
        conversation = result.scalars().first()

        if not conversation:
            conversation = Conversation(
                id=conv_uuid,
                user_id=None,
                title=request.message[:100],
            )
            db.add(conversation)
            await db.flush()

        # ── 2. Store user message ──────────────────────────────────────────────
        user_msg = Message(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role="user",
            content=request.message,
        )
        db.add(user_msg)
        await db.flush()

        # ── 3. Fetch last 20 messages for context ─────────────────────────────
        hist_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .limit(20)
        )
        history = list(reversed(hist_result.scalars().all()))

        anthropic_messages = [
            {"role": m.role, "content": m.content}
            for m in history
            if m.role in ("user", "assistant")
        ]

        # ── 4. Call Anthropic API ─────────────────────────────────────────────
        if not settings.ANTHROPIC_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="ANTHROPIC_API_KEY is not configured",
            )

        async_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        response_msg = await async_client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2048,
            system=ACQUISITION_SYSTEM_PROMPT,
            messages=anthropic_messages,
        )
        assistant_text = response_msg.content[0].text

        # ── 5. Store assistant message ─────────────────────────────────────────
        asst_msg = Message(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_text,
        )
        db.add(asst_msg)
        await db.flush()

        await db.commit()
        await db.refresh(asst_msg)

        logger.info("chat_send_success", conversation_id=str(conversation.id))

        return SendResponse(
            conversationId=str(conversation.id),
            messageId=str(asst_msg.id),
            content=assistant_text,
            toolRuns=[],
            citations=[],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("chat_send_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process message: {str(e)}",
        )


@router.get("/history/{conversation_id}", response_model=list[MessageOut])
async def chat_history(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    """
    Return messages for a conversation as a flat array.
    Accepts conversation_id as a string (UUID or deterministic UUID from string).
    Returns [{id, role, content, timestamp}] matching the frontend Message type.
    """
    try:
        try:
            conv_uuid = uuid.UUID(conversation_id)
        except ValueError:
            conv_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, conversation_id)

        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_uuid)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()

        return [
            MessageOut(
                id=str(m.id),
                role=m.role,
                content=m.content,
                timestamp=m.created_at.isoformat(),
            )
            for m in messages
        ]
    except Exception as e:
        logger.error("chat_history_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve history",
        )


class FeedbackRequest(BaseModel):
    rating: int  # 1 = thumbs up, -1 = thumbs down


@router.post("/messages/{message_id}/feedback")
async def rate_message(
    message_id: str,
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Rate an assistant message thumbs-up (1) or thumbs-down (-1).
    Used to build a quality-filtered training dataset.
    """
    try:
        if request.rating not in (1, -1):
            raise HTTPException(status_code=400, detail="rating must be 1 or -1")

        try:
            msg_uuid = uuid.UUID(message_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid message ID")

        result = await db.execute(select(Message).where(Message.id == msg_uuid))
        msg = result.scalars().first()
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")

        msg.feedback = request.rating
        await db.commit()
        logger.info("message_rated", message_id=message_id, rating=request.rating)
        return {"message_id": message_id, "rating": request.rating, "status": "saved"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("rate_message_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to save rating")


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
