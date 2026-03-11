"""Tool management and execution routing."""
from typing import Optional
from fastapi import APIRouter, HTTPException, status
import structlog

from ..tools.registry import get_registry
from ..schemas.common import (
    ToolListResponse,
    ToolDetailResponse,
    ToolRunResponse,
)

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get("", response_model=ToolListResponse)
async def list_tools() -> ToolListResponse:
    """
    List all registered tools with schemas.

    Returns:
        List of available tools with details
    """
    try:
        registry = get_registry()
        tools = registry.list_all()

        tool_details = [
            ToolDetailResponse(
                id=tool.id,
                name=tool.name,
                description=tool.description,
                input_schema=tool.input_schema,
                output_schema=tool.output_schema,
                auth_requirements=tool.auth_requirements,
                rate_limit_profile=tool.rate_limit_profile,
                examples=tool.get_examples(),
            )
            for tool in tools
        ]

        return ToolListResponse(tools=tool_details, count=len(tool_details))
    except Exception as e:
        logger.error("list_tools_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list tools",
        )


@router.get("/{tool_id}", response_model=ToolDetailResponse)
async def get_tool(tool_id: str) -> ToolDetailResponse:
    """
    Get tool details and schema.

    Args:
        tool_id: Tool identifier

    Returns:
        Tool details with schema
    """
    try:
        registry = get_registry()
        tool = registry.get(tool_id)

        if not tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool '{tool_id}' not found",
            )

        return ToolDetailResponse(
            id=tool.id,
            name=tool.name,
            description=tool.description,
            input_schema=tool.input_schema,
            output_schema=tool.output_schema,
            auth_requirements=tool.auth_requirements,
            rate_limit_profile=tool.rate_limit_profile,
            examples=tool.get_examples(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_tool_failed", tool_id=tool_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get tool",
        )


@router.post("/{tool_id}/run", response_model=ToolRunResponse)
async def run_tool(tool_id: str, params: dict) -> ToolRunResponse:
    """
    Execute a tool directly.

    Args:
        tool_id: Tool identifier
        params: Tool input parameters

    Returns:
        Tool execution result
    """
    try:
        registry = get_registry()
        tool = registry.get(tool_id)

        if not tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool '{tool_id}' not found",
            )

        # Execute tool
        result = await tool.execute(params)

        logger.info(
            "tool_executed",
            tool_id=tool_id,
            status=result.status,
            duration_ms=result.duration_ms,
        )

        return ToolRunResponse(
            tool_id=result.tool_id,
            input_params=result.input_params,
            output=result.output,
            citations=[
                {
                    "source_name": c.source_name,
                    "source_url": c.source_url,
                    "source_label": c.source_label,
                    "retrieved_at": c.retrieved_at,
                    "snippet": c.snippet,
                }
                for c in result.citations
            ],
            duration_ms=result.duration_ms,
            status=result.status,
            error_message=result.error_message,
            cached=result.cached,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("run_tool_failed", tool_id=tool_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute tool",
        )


@router.get("/{tool_id}/health")
async def check_tool_health(tool_id: str) -> dict:
    """
    Check health status of a specific tool.

    Args:
        tool_id: Tool identifier

    Returns:
        Health status
    """
    try:
        registry = get_registry()
        tool = registry.get(tool_id)

        if not tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool '{tool_id}' not found",
            )

        return await tool.healthcheck()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("tool_health_check_failed", tool_id=tool_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check tool health",
        )


@router.get("/health", response_model=dict)
async def check_all_tools_health() -> dict:
    """
    Check health status of all tools.

    Returns:
        Dict mapping tool_id to health status
    """
    try:
        registry = get_registry()
        health_status = await registry.health_check_all()
        return {"tools": health_status}
    except Exception as e:
        logger.error("all_tools_health_check_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check tools health",
        )
