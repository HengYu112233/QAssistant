"""
Example plugin/tool template for extending agent capabilities.
Future: Implement Function Calling / Tool Use for weather, search, etc.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ExampleTool:
    """
    Example tool template.
    
    Can be used as a basis for implementing:
    - Weather API integration
    - Search functionality
    - Reminder/scheduling
    - Data query
    - etc.
    """

    def __init__(self, name: str, description: str):
        """
        Initialize tool.

        Args:
            name: Tool name.
            description: Tool description.
        """
        self.name = name
        self.description = description
        logger.info(f"Initialized tool: {name}")

    async def call(self, *args, **kwargs) -> Any:
        """
        Execute the tool.

        Returns:
            Tool result.
        """
        logger.info(f"Tool {self.name} called with args={args}, kwargs={kwargs}")
        # TODO: Implement actual tool logic
        return {"status": "success", "data": None}

    def to_tool_schema(self) -> Dict[str, Any]:
        """
        Export tool as OpenAI Function Calling schema.
        
        Returns:
            Tool schema for LLM Function Calling.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                }
            }
        }


class ToolRegistry:
    """Registry for managing multiple tools."""

    def __init__(self):
        """Initialize tool registry."""
        self._tools: Dict[str, ExampleTool] = {}

    def register(self, tool: ExampleTool) -> None:
        """
        Register a tool.

        Args:
            tool: Tool instance to register.
        """
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    def get(self, name: str) -> Optional[ExampleTool]:
        """
        Get a tool by name.

        Args:
            name: Tool name.

        Returns:
            Tool instance or None.
        """
        return self._tools.get(name)

    async def call_tool(self, name: str, *args, **kwargs) -> Any:
        """
        Call a tool by name.

        Args:
            name: Tool name.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Tool result.
        """
        tool = self.get(name)
        if not tool:
            logger.warning(f"Tool not found: {name}")
            return {"status": "error", "message": f"Tool '{name}' not found"}
        
        return await tool.call(*args, **kwargs)

    def to_tool_schemas(self) -> list:
        """
        Export all tools as OpenAI Function Calling schemas.

        Returns:
            List of tool schemas.
        """
        return [tool.to_tool_schema() for tool in self._tools.values()]
