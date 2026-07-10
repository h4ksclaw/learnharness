"""Test tools (web search, wikipedia, etc)."""

import pytest

from app.tools import search_arxiv
from app.tools import search_wikipedia
from app.tools import web_search


@pytest.mark.asyncio
async def test_wikipedia():
    result = await search_wikipedia("Python programming language")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_web_search():
    results = await web_search("FastAPI tutorial", max_results=2)
    assert isinstance(results, list)
    assert len(results) <= 2


@pytest.mark.asyncio
async def test_arxiv():
    results = await search_arxiv("knowledge tracing", max_results=2)
    assert isinstance(results, list)
    assert len(results) <= 2
