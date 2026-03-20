"""
Tool Registry - Central registry for all agent tools
"""

from typing import Any, Callable

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logger import loguru_logger


class ToolMetadata(BaseModel):
    """Metadata for a tool"""

    name: str
    description: str
    parameters: dict[str, Any]
    requires_confirmation: bool = False
    dangerous: bool = False


class ToolRegistry:
    """Registry for managing agent tools"""

    def __init__(self) -> None:
        self._tools: dict[str, StructuredTool] = {}
        self._metadata: dict[str, ToolMetadata] = {}

    def register(
        self,
        tool: StructuredTool,
        requires_confirmation: bool = False,
        dangerous: bool = False,
    ) -> None:
        """Register a new tool"""

        name = tool.name
        self._tools[name] = tool
        self._metadata[name] = ToolMetadata(
            name=name,
            description=tool.description,
            parameters=tool.args_schema.schema() if tool.args_schema else {},
            requires_confirmation=requires_confirmation,
            dangerous=dangerous,
        )
        loguru_logger.info(f"Registered tool: {name}")

    def get(self, name: str) -> StructuredTool | None:
        """Get a tool by name"""
        return self._tools.get(name)

    def get_metadata(self, name: str) -> ToolMetadata | None:
        """Get tool metadata"""
        return self._metadata.get(name)

    def list_all(self) -> dict[str, ToolMetadata]:
        """List all registered tools"""
        return self._metadata.copy()

    def requires_confirmation(self, name: str) -> bool:
        """Check if tool requires user confirmation"""
        metadata = self._metadata.get(name)
        return metadata.requires_confirmation if metadata else False

    def is_dangerous(self, name: str) -> bool:
        """Check if tool is marked as dangerous"""
        metadata = self._metadata.get(name)
        return metadata.dangerous if metadata else False

    def to_langchain_tools(self) -> list[StructuredTool]:
        """Get all tools as LangChain StructuredTool list"""
        return list(self._tools.values())


# Global registry instance
tool_registry = ToolRegistry()


def register_tool(
    requires_confirmation: bool = False,
    dangerous: bool = False,
):
    """Decorator for registering tools"""

    def decorator(func: Callable) -> Callable:
        # Create LangChain tool from function
        tool = StructuredTool.from_function(
            func,
            name=func.__name__,
            description=func.__doc__ or "",
        )
        tool_registry.register(tool, requires_confirmation, dangerous)
        return func

    return decorator

