"""MCP adapter base class and registry — same pattern as agentic-invoice-platform."""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]


@dataclass
class ToolCallResult:
    success: bool
    data: Any = None
    error: Optional[str] = None


class MCPToolBase(ABC):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.logger = logging.getLogger(f"mcp.{name}")

    @abstractmethod
    def get_tools(self) -> List[ToolDefinition]:
        ...

    @abstractmethod
    async def execute(self, tool_name: str, params: dict) -> ToolCallResult:
        ...

    async def safe_execute(self, tool_name: str, params: dict, task_id: str = "") -> dict:
        try:
            result = await self.execute(tool_name, params)
            return {"success": result.success, "data": result.data, "error": result.error}
        except Exception as exc:
            self.logger.error("Tool %s failed (task=%s): %s", tool_name, task_id, exc)
            return {"success": False, "data": None, "error": str(exc)}

    def as_openai_tools(self) -> List[dict]:
        tools = []
        for t in self.get_tools():
            tools.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            })
        return tools


class AdapterRegistry:
    def __init__(self):
        self._adapters: Dict[str, MCPToolBase] = {}

    def register(self, adapter: MCPToolBase):
        self._adapters[adapter.name] = adapter
        logger.info("MCP adapter registered: %s", adapter.name)

    def get(self, name: str) -> Optional[MCPToolBase]:
        return self._adapters.get(name)

    def list_adapters(self) -> List[str]:
        return list(self._adapters.keys())

    def all_tools(self) -> List[dict]:
        tools = []
        for adapter in self._adapters.values():
            tools.extend(adapter.as_openai_tools())
        return tools

    def get_tool_map(self) -> Dict[str, MCPToolBase]:
        """Map tool_name → adapter for quick lookup during ReAct execution."""
        mapping = {}
        for adapter in self._adapters.values():
            for tool in adapter.get_tools():
                mapping[tool.name] = adapter
        return mapping


adapter_registry = AdapterRegistry()
