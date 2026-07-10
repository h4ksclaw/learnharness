"""LLM Router — routes to any OpenAI-compatible endpoint.

Works with: Ollama, vLLM, LM Studio, OpenAI, Anthropic (via proxy), 
DeepSeek, Gemini (via proxy), OpenRouter, any OpenAI-compatible API.
"""

import time
import uuid
from typing import Any

import httpx

from app.config import settings


class LLMRouter:
    """Thin wrapper around OpenAI-compatible chat completions."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        default_model: str | None = None,
    ):
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.api_key = api_key or settings.llm_api_key
        self.default_model = default_model or settings.llm_model

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_format: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Call the LLM and return the response dict.

        Returns:
            {"content": str, "model": str, "usage": {...}, "latency_ms": int}
        """
        model = model or self.default_model
        headers = {"Content-Type": "application/json"}
        if self.api_key and self.api_key != "not-needed":
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if response_format:
            payload["response_format"] = response_format

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        latency_ms = int((time.monotonic() - start) * 1000)
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        return {
            "content": content,
            "model": model,
            "usage": usage,
            "latency_ms": latency_ms,
        }

    async def complete_json(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        """Call the LLM with JSON mode and parse the response.

        Falls back to extracting JSON from text if response_format isn't supported.
        """
        import json

        try:
            result = await self.complete(
                messages,
                model=model,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            return json.loads(result["content"])
        except (json.JSONDecodeError, httpx.HTTPStatusError):
            # Fallback: try without response_format, extract JSON from text
            result = await self.complete(messages, model=model, temperature=temperature)
            content = result["content"]
            # Try to find JSON in the response
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # Last resort: find first { and last }
                start_idx = content.find("{")
                end_idx = content.rfind("}")
                if start_idx >= 0 and end_idx > start_idx:
                    return json.loads(content[start_idx : end_idx + 1])
                raise ValueError(f"Could not parse JSON from LLM response: {content[:200]}")


# Singleton
llm_router = LLMRouter()
