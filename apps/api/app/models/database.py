"""SQLAlchemy ORM models for all database tables."""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Float,
    Boolean,
    ForeignKey,
    Index,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship, mapped_column
import uuid

class _Base:
    __allow_unmapped__ = True

Base = declarative_base(cls=_Base)


class User(Base):
    """User account model."""

    __tablename__ = "users"

    id: uuid.UUID = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: str = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: str = mapped_column(String(255), nullable=False)
    role: str = mapped_column(String(50), default="user", nullable=False)
    is_active: bool = mapped_column(Boolean, default=True, nullable=False)
    created_at: datetime = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: datetime = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    api_credentials = relationship("ApiCredential", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    igce_projects = relationship("IGCEProject", back_populates="user", cascade="all, delete-orphan")
    audit_events = relationship("AuditEvent", back_populates="actor", cascade="all, delete-orphan")


class ApiCredential(Base):
    """Stored API credentials for external services."""

    __tablename__ = "api_credentials"

    id: uuid.UUID = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: uuid.UUID = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: str = mapped_column(String(100), nullable=False)
    encrypted_secret: str = mapped_column(Text, nullable=False)
    scopes: str = mapped_column(String(500), nullable=True)
    created_at: datetime = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: datetime = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user = relationship("User", back_populates="api_credentials")

    __table_args__ = (
        Index("ix_api_credentials_user_id", "user_id"),
        Index("ix_api_credentials_provider", "provider"),
    )


class Conversation(Base):
    """Chat conversation model."""

    __tablename__ = "conversations"

    id: uuid.UUID = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Optional[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    title: str = mapped_column(String(500), nullable=False)
    created_at: datetime = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: datetime = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    tool_runs = relationship("ToolRun", back_populates="conversation", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_conversations_user_id", "user_id"),)


class Message(Base):
    """Chat message model."""

    __tablename__ = "messages"

    id: uuid.UUID = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: uuid.UUID = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: str = mapped_column(String(50), nullable=False)  # "user", "assistant", "system"
    content: str = mapped_column(Text, nullable=False)
    feedback: Optional[int] = mapped_column(
        nullable=True, default=None  # 1 = thumbs up, -1 = thumbs down, NULL = no rating
    )
    created_at: datetime = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")

    __table_args__ = (Index("ix_messages_conversation_id", "conversation_id"),)


class ToolRun(Base):
    """Record of a tool execution."""

    __tablename__ = "tool_runs"

    id: uuid.UUID = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: uuid.UUID = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    tool_id: str = mapped_column(String(100), nullable=False)
    input_json: dict = mapped_column(JSONB, nullable=False)
    output_json: Optional[dict] = mapped_column(JSONB, nullable=True)
    status: str = mapped_column(String(50), nullable=False)  # "success", "error", "timeout"
    duration_ms: float = mapped_column(Float, nullable=False)
    error_message: Optional[str] = mapped_column(Text, nullable=True)
    created_at: datetime = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="tool_runs")
    citations = relationship("Citation", back_populates="tool_run", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_tool_runs_conversation_id", "conversation_id"),
        Index("ix_tool_runs_tool_id", "tool_id"),
    )


class Citation(Base):
    """Citation from a tool run."""

    __tablename__ = "citations"

    id: uuid.UUID = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tool_run_id: uuid.UUID = mapped_column(
        UUID(as_uuid=True), ForeignKey("tool_runs.id", ondelete="CASCADE"), nullable=False
    )
    source_name: str = mapped_column(String(255), nullable=False)
    source_url: str = mapped_column(String(2000), nullable=False)
    source_label: str = mapped_column(String(500), nullable=False)
    retrieved_at: datetime = mapped_column(DateTime, nullable=False)
    snippet: Optional[str] = mapped_column(Text, nullable=True)

    tool_run = relationship("ToolRun", back_populates="citations")

    __table_args__ = (Index("ix_citations_tool_run_id", "tool_run_id"),)


class IGCEProject(Base):
    """Saved IGCE (Independent Government Cost Estimate) project."""

    __tablename__ = "igce_projects"

    id: uuid.UUID = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Optional[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    title: str = mapped_column(String(500), nullable=False)
    assumptions_json: dict = mapped_column(JSONB, nullable=False)
    result_json: Optional[dict] = mapped_column(JSONB, nullable=True)
    created_at: datetime = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: datetime = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user = relationship("User", back_populates="igce_projects")

    __table_args__ = (Index("ix_igce_projects_user_id", "user_id"),)


class AuditEvent(Base):
    """Audit log entry."""

    __tablename__ = "audit_events"

    id: uuid.UUID = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id: Optional[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    event_type: str = mapped_column(String(100), nullable=False)  # "create", "update", "delete", etc.
    entity_type: str = mapped_column(String(100), nullable=False)  # "conversation", "tool_run", etc.
    entity_id: str = mapped_column(String(100), nullable=False)
    details_json: dict = mapped_column(JSONB, nullable=False)
    created_at: datetime = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    actor = relationship("User", back_populates="audit_events")

    __table_args__ = (
        Index("ix_audit_events_actor_id", "actor_id"),
        Index("ix_audit_events_event_type", "event_type"),
        Index("ix_audit_events_entity_type", "entity_type"),
        Index("ix_audit_events_created_at", "created_at"),
    )


class FARSection(Base):
    """FAR/DFARS section for RAG search."""

    __tablename__ = "far_sections"

    id: int = mapped_column(Integer, primary_key=True, autoincrement=True)
    regulation: str = mapped_column(String(20), nullable=False)  # 'FAR', 'DFARS', 'GSAM'
    part: int = mapped_column(Integer, nullable=False)
    subpart: Optional[str] = mapped_column(String(20), nullable=True)
    section: str = mapped_column(String(50), nullable=False)  # e.g. '15.404-1'
    title: str = mapped_column(String(500), nullable=False)
    content: str = mapped_column(Text, nullable=False)
    effective_date: Optional[datetime] = mapped_column(DateTime, nullable=True)
    source_url: Optional[str] = mapped_column(String(1000), nullable=True)
    chunk_index: int = mapped_column(Integer, default=0, nullable=False)  # for multi-chunk sections
    embedding_json: Optional[str] = mapped_column(Text, nullable=True)  # 768-dim vector as JSON string
    created_at: datetime = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_far_sections_regulation", "regulation"),
        Index("ix_far_sections_part", "part"),
        Index("ix_far_sections_section", "section"),
    )
