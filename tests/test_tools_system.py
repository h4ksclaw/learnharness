"""Test tools system — registry, schemas, execution, edge cases."""

import pytest

from app.tools import TOOL_DEFINITIONS
from app.tools import browse_url
from app.tools import execute_tool
from app.tools import get_openai_tool_schemas


class TestToolRegistry:
    def test_all_tools_registered(self):
        assert "web_search" in TOOL_DEFINITIONS
        assert "browse_url" in TOOL_DEFINITIONS
        assert "wikipedia" in TOOL_DEFINITIONS
        assert "arxiv" in TOOL_DEFINITIONS

    def test_each_tool_has_function(self):
        for name, defn in TOOL_DEFINITIONS.items():
            assert callable(defn["function"]), f"{name} has no callable function"

    def test_each_tool_has_parameters(self):
        for name, defn in TOOL_DEFINITIONS.items():
            assert "parameters" in defn, f"{name} missing parameters"
            assert "properties" in defn["parameters"]

    def test_each_tool_has_required_fields(self):
        for _name, defn in TOOL_DEFINITIONS.items():
            assert "required" in defn["parameters"]
            assert isinstance(defn["parameters"]["required"], list)


class TestOpenAISchemas:
    def test_schemas_for_all_tools(self):
        schemas = get_openai_tool_schemas(["web_search", "browse_url", "wikipedia", "arxiv"])
        assert len(schemas) == 4

    def test_schema_format(self):
        schemas = get_openai_tool_schemas(["web_search"])
        assert schemas[0]["type"] == "function"
        assert schemas[0]["function"]["name"] == "web_search"
        assert "query" in schemas[0]["function"]["parameters"]["properties"]

    def test_empty_tools(self):
        assert get_openai_tool_schemas([]) == []

    def test_unknown_tool_ignored(self):
        schemas = get_openai_tool_schemas(["nonexistent_tool"])
        assert len(schemas) == 0


class TestExecuteTool:
    @pytest.mark.asyncio
    async def test_execute_wikipedia(self):
        result = await execute_tool("wikipedia", {"query": "Python"})
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        result = await execute_tool("nonexistent", {})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_with_wrong_args(self):
        result = await execute_tool("web_search", {"nonexistent_arg": True})
        # Should either return results or an error, not crash
        assert isinstance(result, list | dict)

    @pytest.mark.asyncio
    async def test_execute_web_search(self):
        result = await execute_tool("web_search", {"query": "test", "max_results": 1})
        assert isinstance(result, list)
        assert len(result) <= 1

    @pytest.mark.asyncio
    async def test_execute_arxiv(self):
        result = await execute_tool("arxiv", {"query": "learning", "max_results": 1})
        assert isinstance(result, list)


class TestBrowseUrl:
    @pytest.mark.asyncio
    async def test_invalid_url(self):
        result = await browse_url("not-a-url")
        assert isinstance(result, str)
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_max_chars_limit(self):
        # Use a reliable URL
        result = await browse_url("https://httpbin.org/html", max_chars=100)
        assert len(result) <= 200  # Allow some overhead
