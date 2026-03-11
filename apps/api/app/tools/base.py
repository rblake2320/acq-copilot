"""Abstract base class and models for all tools."""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field
import httpx
import time


class ToolInput(BaseModel):
    """Base model for all tool inputs."""

    pass


class ToolOutput(BaseModel):
    """Base model for all tool outputs."""

    raw_response: Optional[dict | list] = None
    retrieved_at: datetime
    source_url: str
    source_name: str


class Citation(BaseModel):
    """Citation for a data source used by a tool."""

    source_name: str = Field(..., description="Name of the source (e.g., 'USAspending API')")
    source_url: str = Field(..., description="URL of the source")
    source_label: str = Field(..., description="Human-readable label for the source")
    retrieved_at: datetime = Field(..., description="When the data was retrieved")
    snippet: Optional[str] = Field(
        default=None, description="Optional text snippet from the source"
    )


class ToolRunResult(BaseModel):
    """Result of executing a tool."""

    tool_id: str = Field(..., description="Unique identifier of the tool")
    input_params: dict = Field(..., description="Input parameters used")
    output: Any = Field(..., description="Tool output (structure depends on tool)")
    citations: list[Citation] = Field(default_factory=list, description="List of citations")
    duration_ms: float = Field(..., description="Execution time in milliseconds")
    status: str = Field(..., pattern="^(success|error|timeout)$", description="Execution status")
    error_message: Optional[str] = Field(default=None, description="Error details if status is error")
    cached: bool = Field(default=False, description="Whether result was served from cache")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class BaseTool(ABC):
    """Abstract base class for all acquisition intelligence tools."""

    id: str
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    auth_requirements: list[str]
    rate_limit_profile: dict

    def __init__(self, http_client: Optional[httpx.AsyncClient] = None) -> None:
        """Initialize tool with optional HTTP client."""
        self._client = http_client or httpx.AsyncClient(timeout=30.0)

    async def execute(self, params: dict) -> ToolRunResult:
        """
        Execute the tool with timing, error handling, and citation building.

        Args:
            params: Input parameters for the tool

        Returns:
            ToolRunResult with output, citations, and metadata
        """
        start = time.monotonic()
        try:
            output = await self.run(params)
            citations = self.build_citations(params, output)
            duration = (time.monotonic() - start) * 1000
            return ToolRunResult(
                tool_id=self.id,
                input_params=params,
                output=output,
                citations=citations,
                duration_ms=round(duration, 2),
                status="success",
            )
        except TimeoutError as e:
            duration = (time.monotonic() - start) * 1000
            return ToolRunResult(
                tool_id=self.id,
                input_params=params,
                output=None,
                citations=[],
                duration_ms=round(duration, 2),
                status="timeout",
                error_message=str(e),
            )
        except Exception as e:
            duration = (time.monotonic() - start) * 1000
            return ToolRunResult(
                tool_id=self.id,
                input_params=params,
                output=None,
                citations=[],
                duration_ms=round(duration, 2),
                status="error",
                error_message=str(e),
            )

    @abstractmethod
    async def run(self, params: dict) -> Any:
        """
        Execute the tool logic.

        Args:
            params: Input parameters

        Returns:
            Tool-specific output
        """
        ...

    @abstractmethod
    def build_citations(self, params: dict, output: Any) -> list[Citation]:
        """
        Build citations for the output data.

        Args:
            params: Input parameters
            output: Tool output

        Returns:
            List of Citation objects
        """
        ...

    async def healthcheck(self) -> dict[str, Any]:
        """
        Check if the tool's dependencies are healthy.

        Returns:
            Dict with tool_id, status, and optional message
        """
        return {
            "tool_id": self.id,
            "status": "unknown",
            "message": "healthcheck not implemented",
        }

    def get_examples(self) -> list[dict]:
        """
        Get example inputs and outputs for documentation.

        Returns:
            List of example dicts
        """
        return []

    async def close(self) -> None:
        """Clean up resources."""
        if self._client:
            await self._client.aclose()
