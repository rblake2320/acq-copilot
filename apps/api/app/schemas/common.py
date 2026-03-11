"""Common Pydantic schemas for API requests and responses."""
from datetime import datetime
from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel, Field
import uuid

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""

    items: list[T] = Field(..., description="List of items")
    total: int = Field(..., description="Total count of items")
    skip: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Maximum items in this page")
    pages: int = Field(..., description="Total number of pages")

    @property
    def has_next(self) -> bool:
        """Check if there's a next page."""
        return (self.skip + self.limit) < self.total


class ErrorResponse(BaseModel):
    """Error response model."""

    detail: str = Field(..., description="Error message")
    status_code: int = Field(..., description="HTTP status code")
    error_type: Optional[str] = Field(default=None, description="Error type/code")
    request_id: Optional[str] = Field(default=None, description="Request tracking ID")


class CitationResponse(BaseModel):
    """Citation for data source."""

    source_name: str = Field(..., description="Name of the source")
    source_url: str = Field(..., description="URL of the source")
    source_label: str = Field(..., description="Human-readable label")
    retrieved_at: datetime = Field(..., description="Retrieval timestamp")
    snippet: Optional[str] = Field(default=None, description="Text snippet from source")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ToolRunResponse(BaseModel):
    """Response from a tool execution."""

    tool_id: str = Field(..., description="Tool identifier")
    input_params: dict = Field(..., description="Input parameters")
    output: Any = Field(..., description="Tool output")
    citations: list[CitationResponse] = Field(default_factory=list, description="Citations")
    duration_ms: float = Field(..., description="Execution time in milliseconds")
    status: str = Field(..., description="Execution status (success, error, timeout)")
    error_message: Optional[str] = Field(default=None, description="Error details")
    cached: bool = Field(default=False, description="Whether from cache")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ConversationCreate(BaseModel):
    """Create conversation request."""

    title: str = Field(..., min_length=1, max_length=500, description="Conversation title")


class ConversationResponse(BaseModel):
    """Conversation response."""

    id: uuid.UUID = Field(..., description="Conversation ID")
    title: str = Field(..., description="Conversation title")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class MessageCreate(BaseModel):
    """Create message request."""

    content: str = Field(..., min_length=1, description="Message content")


class MessageResponse(BaseModel):
    """Message response."""

    id: uuid.UUID = Field(..., description="Message ID")
    role: str = Field(..., description="Message role (user, assistant, system)")
    content: str = Field(..., description="Message content")
    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ChatRequest(BaseModel):
    """Chat request."""

    conversation_id: Optional[uuid.UUID] = Field(
        default=None, description="Existing conversation ID; creates new if omitted"
    )
    message: str = Field(..., min_length=1, description="User message")
    tools: Optional[list[str]] = Field(
        default=None, description="Specific tool IDs to use; uses all if omitted"
    )


class ChatResponse(BaseModel):
    """Chat response."""

    conversation_id: uuid.UUID = Field(..., description="Conversation ID")
    message_id: uuid.UUID = Field(..., description="Assistant message ID")
    message: str = Field(..., description="Assistant response")
    tool_runs: list[ToolRunResponse] = Field(default_factory=list, description="Tools executed")
    citations: list[CitationResponse] = Field(default_factory=list, description="All citations")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class ToolDetailResponse(BaseModel):
    """Detailed tool information."""

    id: str = Field(..., description="Tool ID")
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    input_schema: dict = Field(..., description="Input parameter schema")
    output_schema: dict = Field(..., description="Output schema")
    auth_requirements: list[str] = Field(..., description="Required authentication")
    rate_limit_profile: dict = Field(..., description="Rate limiting configuration")
    examples: list[dict] = Field(default_factory=list, description="Usage examples")


class ToolListResponse(BaseModel):
    """List of tools."""

    tools: list[ToolDetailResponse] = Field(..., description="Available tools")
    count: int = Field(..., description="Total tools")


class HealthResponse(BaseModel):
    """System health check response."""

    status: str = Field(..., description="Health status (healthy, degraded, unhealthy)")
    timestamp: datetime = Field(..., description="Check timestamp")
    version: str = Field(..., description="API version")
    services: dict[str, str] = Field(..., description="Status of each service")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class AuditEventResponse(BaseModel):
    """Audit event response."""

    id: uuid.UUID = Field(..., description="Event ID")
    actor_id: Optional[uuid.UUID] = Field(default=None, description="Actor user ID")
    event_type: str = Field(..., description="Event type")
    entity_type: str = Field(..., description="Entity type")
    entity_id: str = Field(..., description="Entity ID")
    details: dict = Field(..., description="Event details")
    created_at: datetime = Field(..., description="Event timestamp")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class CacheStatsResponse(BaseModel):
    """Cache statistics."""

    hit_rate: float = Field(..., description="Cache hit rate (0-1)")
    total_hits: int = Field(..., description="Total cache hits")
    total_misses: int = Field(..., description="Total cache misses")
    keys_count: int = Field(..., description="Number of cached keys")
    memory_bytes: int = Field(..., description="Memory used in bytes")
