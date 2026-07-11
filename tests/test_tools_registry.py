"""Tests for the tools system — tool registry, schema generation, execution."""

import pytest

from app.tools import TOOL_DEFINITIONS
from app.tools import execute_tool
from app.tools import get_openai_tool_schemas


class TestToolRegistry:
    """Test tool registration and discovery."""

    def test_registry_not_empty(self):
        assert len(TOOL_DEFINITIONS) > 0

    def test_list_available_tools_returns_names(self):
        tools = list(TOOL_DEFINITIONS.keys())
        assert isinstance(tools, list)
        assert len(tools) > 0
        for name in tools:
            assert isinstance(name, str)

    def test_get_openai_tool_schemas_format(self):
        tool_names = list(TOOL_DEFINITIONS.keys())
        schemas = get_openai_tool_schemas(tool_names)
        assert isinstance(schemas, list)
        for schema in schemas:
            assert "type" in schema
            assert schema["type"] == "function"
            assert "function" in schema
            fn = schema["function"]
            assert "name" in fn
            assert "description" in fn
            assert "parameters" in fn


class TestExecuteTool:
    """Test tool execution."""

    @pytest.mark.asyncio
    async def test_execute_unknown_tool_returns_error(self):
        result = await execute_tool("nonexistent_tool", {})
        assert isinstance(result, dict)
        assert "error" in result
