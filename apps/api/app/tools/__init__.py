"""Acquisition Copilot tool registry and initialization.

This module imports all tool implementations and provides a function
to register them with a tool registry for orchestration and routing.
"""

from typing import Dict, Type, Any

from app.tools.base import BaseTool
from app.tools.usaspending import USASpendingTool
from app.tools.federal_register import FederalRegisterTool
from app.tools.ecfr import eCFRTool
from app.tools.bls_oews import BLSOEWSTool
from app.tools.gsa_perdiem import GSAPerDiemTool
from app.tools.gsa_calc import GSACalcTool
from app.tools.regulations_gov import RegulationsGovTool
from app.tools.igce_builder import IGCEBuilderTool
from app.tools.sam_opportunities import SamSearchTool


# Tool registry mapping
TOOL_REGISTRY: Dict[str, Type[BaseTool]] = {
    "usaspending.search_awards": USASpendingTool,
    "federal_register.search_documents": FederalRegisterTool,
    "ecfr.get_section": eCFRTool,
    "bls.oews.lookup_wages": BLSOEWSTool,
    "gsa.perdiem.lookup_location": GSAPerDiemTool,
    "gsa.calc.search_rates": GSACalcTool,
    "regulations.search_dockets": RegulationsGovTool,
    "igce.build": IGCEBuilderTool,
    "sam.search_opportunities": SamSearchTool,
}


def register_all_tools(registry: Dict[str, Any]) -> None:
    """Register all tools with the provided registry.

    Args:
        registry: The tool registry dictionary to populate

    Returns:
        None (modifies registry in place)

    Example:
        >>> tool_registry = {}
        >>> register_all_tools(tool_registry)
        >>> 'usaspending.search_awards' in tool_registry
        True
    """
    for tool_id, tool_class in TOOL_REGISTRY.items():
        tool_instance = tool_class()
        registry[tool_id] = tool_instance


def get_tool_by_id(tool_id: str) -> BaseTool:
    """Get a tool instance by ID.

    Args:
        tool_id: The tool identifier (e.g., 'usaspending.search_awards')

    Returns:
        Instantiated tool

    Raises:
        KeyError: If tool_id not found in registry
    """
    if tool_id not in TOOL_REGISTRY:
        available = ", ".join(TOOL_REGISTRY.keys())
        raise KeyError(f"Unknown tool: {tool_id}. Available tools: {available}")
    
    tool_class = TOOL_REGISTRY[tool_id]
    
    return tool_class()


def list_tools() -> Dict[str, Dict[str, str]]:
    """List all available tools with metadata.

    Returns:
        Dictionary mapping tool IDs to metadata (name, description)
    """
    tools = {}
    for tool_id, tool_class in TOOL_REGISTRY.items():
        tool = get_tool_by_id(tool_id)
        tools[tool_id] = {
            "name": tool.name,
            "description": tool.description,
            "auth_requirements": tool.auth_requirements.value,
            "rate_limit_profile": tool.rate_limit_profile.value,
        }
    return tools


__all__ = [
    "BaseTool",
    "USASpendingTool",
    "FederalRegisterTool",
    "eCFRTool",
    "BLSOEWSTool",
    "GSAPerDiemTool",
    "GSACalcTool",
    "RegulationsGovTool",
    "IGCEBuilderTool",
    "SamSearchTool",
    "TOOL_REGISTRY",
    "register_all_tools",
    "get_tool_by_id",
    "list_tools",
]
