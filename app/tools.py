"""Agent tools — pluggable capabilities the agent can use.

The agent's master prompt defines what it does. Tools give it the ability
to search the web, browse URLs, read papers, etc.

Tools are exposed to the LLM as function calls. The LLM decides when to use them.
"""

import asyncio
import json
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify as md


async def web_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Search the web using DuckDuckGo HTML (no API key needed)."""
    results = []
    url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers, follow_redirects=True)
            soup = BeautifulSoup(resp.text, "html.parser")

        for item in soup.select(".result")[:max_results]:
            title_el = item.select_one(".result__title a")
            snippet_el = item.select_one(".result__snippet")
            if title_el:
                title = title_el.get_text(strip=True)
                href = title_el.get("href", "")
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                results.append({
                    "title": title,
                    "url": href,
                    "snippet": snippet,
                })
    except Exception as e:
        results.append({"error": f"Search failed: {e}"})

    return results


async def browse_url(url: str, max_chars: int = 5000) -> str:
    """Fetch a URL and return its content as markdown."""
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove scripts, styles, nav
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        # Try article/main first, fall back to body
        main = soup.find("article") or soup.find("main") or soup.find("body")
        if main:
            text = md(str(main), strip=["img", "iframe"])
            # Clean up excessive whitespace
            text = re.sub(r"\n{3,}", "\n\n", text)
            return text[:max_chars]
        return "Could not extract content."
    except Exception as e:
        return f"Error fetching {url}: {e}"


async def search_wikipedia(query: str, sentences: int = 5) -> str:
    """Search Wikipedia and return a summary."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Search for the article
            search_url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": 1,
            }
            resp = await client.get(search_url, params=params)
            data = resp.json()

            if not data.get("query", {}).get("search"):
                return f"No Wikipedia article found for '{query}'"

            title = data["query"]["search"][0]["title"]

            # Get the summary
            summary_url = (
                f"https://en.wikipedia.org/api/rest_v1/page/summary/"
                f"{title.replace(' ', '_')}"
            )
            resp = await client.get(summary_url)
            summary_data = resp.json()

            extract = summary_data.get("extract", "")
            return f"**{title}**\n\n{extract}" if extract else f"Found '{title}' but no summary available."
    except Exception as e:
        return f"Wikipedia search failed: {e}"


async def search_arxiv(query: str, max_results: int = 3) -> list[dict[str, str]]:
    """Search arXiv for academic papers."""
    results = []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            url = "http://export.arxiv.org/api/query"
            params = {
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": max_results,
                "sortBy": "relevance",
            }
            resp = await client.get(url, params=params)
            soup = BeautifulSoup(resp.text, "xml")

        for entry in soup.find_all("entry")[:max_results]:
            title = entry.find("title").get_text(strip=True) if entry.find("title") else ""
            summary = entry.find("summary").get_text(strip=True) if entry.find("summary") else ""
            link = entry.find("id").get_text(strip=True) if entry.find("id") else ""
            published = entry.find("published").get_text(strip=True) if entry.find("published") else ""
            results.append({
                "title": title,
                "summary": summary[:500],
                "url": link,
                "published": published[:10],
            })
    except Exception as e:
        results.append({"error": f"arXiv search failed: {e}"})

    return results


# ─── Tool Registry ───

TOOL_DEFINITIONS = {
    "web_search": {
        "description": "Search the web for current information",
        "function": web_search,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Max results", "default": 5},
            },
            "required": ["query"],
        },
    },
    "browse_url": {
        "description": "Fetch a URL and return its content as markdown",
        "function": browse_url,
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"},
                "max_chars": {"type": "integer", "description": "Max chars to return", "default": 5000},
            },
            "required": ["url"],
        },
    },
    "wikipedia": {
        "description": "Search Wikipedia for a summary of a topic",
        "function": search_wikipedia,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Topic to search"},
                "sentences": {"type": "integer", "description": "Summary length", "default": 5},
            },
            "required": ["query"],
        },
    },
    "arxiv": {
        "description": "Search arXiv for academic papers",
        "function": search_arxiv,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Max results", "default": 3},
            },
            "required": ["query"],
        },
    },
}


def get_openai_tool_schemas(enabled_tools: list[str]) -> list[dict]:
    """Get OpenAI function-calling tool schemas for the enabled tools."""
    schemas = []
    for tool_name in enabled_tools:
        if tool_name in TOOL_DEFINITIONS:
            td = TOOL_DEFINITIONS[tool_name]
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": td["description"],
                    "parameters": td["parameters"],
                },
            })
    return schemas


async def execute_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    """Execute a tool by name with the given arguments."""
    if tool_name not in TOOL_DEFINITIONS:
        return {"error": f"Unknown tool: {tool_name}"}

    func = TOOL_DEFINITIONS[tool_name]["function"]
    try:
        result = await func(**arguments)
        return result
    except Exception as e:
        return {"error": f"Tool execution failed: {e}"}
