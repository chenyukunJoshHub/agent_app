"""Tool Registry for centralized tool management.

Per architecture doc §2.1:
- Provides centralized tool registration
- Prevents duplicate tool names
- Allows retrieval by name or all tools at once
- Returns independent lists to prevent external modification
"""
from typing import Dict, List

from langchain_core.tools import BaseTool
from loguru import logger


class ToolRegistry:
    """Centralized registry for agent tools.

    Provides:
    - register(): Register a tool with unique name validation
    - get_all(): Get all registered tools
    - get_by_name(): Get a specific tool by name

    Example:
        registry = ToolRegistry()
        registry.register(web_search)
        registry.register(read_file)

        all_tools = registry.get_all()
        search_tool = registry.get_by_name("web_search")
    """

    def __init__(self) -> None:
        """Initialize an empty tool registry."""
        self._tools: Dict[str, BaseTool] = {}
        logger.debug("ToolRegistry initialized")

    def register(self, tool: BaseTool) -> str:
        """Register a tool in the registry.

        Args:
            tool: BaseTool instance to register

        Returns:
            str: The tool's name

        Raises:
            ValueError: If tool is None or not a BaseTool instance
            ValueError: If a tool with the same name is already registered
        """
        if tool is None:
            raise ValueError("Tool cannot be None")

        if not isinstance(tool, BaseTool):
            raise ValueError("Tool must be a BaseTool instance")

        tool_name = tool.name

        if tool_name in self._tools:
            raise ValueError(
                f"Tool '{tool_name}' is already registered. "
                f"Use a different name or unregister the existing tool first."
            )

        self._tools[tool_name] = tool
        logger.info(f"Registered tool: {tool_name}")
        return tool_name

    def get_all(self) -> List[BaseTool]:
        """Get all registered tools.

        Returns:
            List[BaseTool]: List of all registered tools in registration order.
                           Returns a copy to prevent external modification.
        """
        # Return a copy to prevent external modification of internal state
        return list(self._tools.values())

    def get_by_name(self, name: str) -> BaseTool:
        """Get a tool by its name.

        Args:
            name: Tool name to retrieve

        Returns:
            BaseTool: The requested tool

        Raises:
            KeyError: If no tool with the given name is registered
        """
        if name not in self._tools:
            available = ", ".join(self._tools.keys()) if self._tools else "none"
            raise KeyError(
                f"Tool '{name}' not found. Available tools: {available}"
            )

        return self._tools[name]

    def unregister(self, name: str) -> None:
        """Unregister a tool by name.

        Args:
            name: Tool name to unregister

        Raises:
            KeyError: If no tool with the given name is registered
        """
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found")

        del self._tools[name]
        logger.info(f"Unregistered tool: {name}")

    def clear(self) -> None:
        """Clear all registered tools."""
        count = len(self._tools)
        self._tools.clear()
        logger.info(f"Cleared {count} tool(s) from registry")

    def __len__(self) -> int:
        """Return the number of registered tools."""
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """Check if a tool is registered by name."""
        return name in self._tools


__all__ = ["ToolRegistry"]
