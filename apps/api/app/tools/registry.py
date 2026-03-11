"""Tool registry for managing and accessing all available tools."""
from typing import Optional
from .base import BaseTool
import structlog

logger = structlog.get_logger(__name__)


class ToolRegistry:
    """Singleton registry for managing tools."""

    def __init__(self) -> None:
        """Initialize empty tool registry."""
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """
        Register a tool in the registry.

        Args:
            tool: Tool instance to register

        Raises:
            ValueError: If tool with same id already exists
        """
        if tool.id in self._tools:
            raise ValueError(f"Tool with id '{tool.id}' already registered")
        self._tools[tool.id] = tool
        logger.info("tool_registered", tool_id=tool.id, tool_name=tool.name)

    def get(self, tool_id: str) -> Optional[BaseTool]:
        """
        Get a tool by id.

        Args:
            tool_id: Unique tool identifier

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(tool_id)

    def list_all(self) -> list[BaseTool]:
        """
        Get all registered tools.

        Returns:
            List of all registered tool instances
        """
        return list(self._tools.values())

    def search(self, query: str) -> list[BaseTool]:
        """
        Search tools by name or description.

        Args:
            query: Search query (case-insensitive)

        Returns:
            List of matching tools
        """
        query_lower = query.lower()
        results = []
        for tool in self._tools.values():
            if (
                query_lower in tool.name.lower()
                or query_lower in tool.description.lower()
            ):
                results.append(tool)
        return results

    async def health_check_all(self) -> dict[str, dict]:
        """
        Check health of all registered tools.

        Returns:
            Dict mapping tool_id to health status
        """
        results = {}
        for tool_id, tool in self._tools.items():
            try:
                results[tool_id] = await tool.healthcheck()
            except Exception as e:
                results[tool_id] = {
                    "tool_id": tool_id,
                    "status": "error",
                    "message": str(e),
                }
                logger.error("tool_healthcheck_failed", tool_id=tool_id, error=str(e))
        return results

    def count(self) -> int:
        """Get total number of registered tools."""
        return len(self._tools)

    async def close_all(self) -> None:
        """Close all tool connections."""
        for tool in self._tools.values():
            try:
                await tool.close()
            except Exception as e:
                logger.warning("tool_close_failed", tool_id=tool.id, error=str(e))


# Module-level singleton instance
_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """Get or create the global tool registry."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
