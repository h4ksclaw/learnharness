"""LLM Router — routes to any OpenAI-compatible endpoint.

Works with: Ollama, vLLM, LM Studio, OpenAI, DeepSeek, Gemini (via proxy),
OpenRouter, any OpenAI-compatible API.

Supports:
- Plain completions (httpx)
- JSON mode completions
- Structured output via `instructor` (Pydantic models with auto-retry)
- Embedding generation
"""

import json
import time
from typing import Any, Type, TypeVar

import httpx
import instructor
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import settings

T = TypeVar("T", bound=BaseModel)


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

        # OpenAI client for instructor and embeddings
        self._client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key if self.api_key != "not-needed" else "ollama",
        )
        # instructor-wrapped client for structured output
        self._structured = instructor.from_openai(self._client)

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
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # Last resort: find first { and last }
                start_idx = content.find("{")
                end_idx = content.rfind("}")
                if start_idx >= 0 and end_idx > start_idx:
                    return json.loads(content[start_idx : end_idx + 1])
                raise ValueError(f"Could not parse JSON from LLM response: {content[:200]}")

    async def complete_structured(
        self,
        response_model: Type[T],
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.3,
        max_retries: int = 2,
    ) -> T:
        """Call the LLM with instructor for guaranteed structured output.

        Uses Pydantic model validation with automatic retry on failure.
        This is the most robust way to get structured data from an LLM.

        Falls back to complete_json + manual parse if instructor fails
        (e.g., Ollama doesn't support structured output well).
        """
        try:
            result = await self._structured.chat.completions.create(
                model=model or self.default_model,
                response_model=response_model,
                messages=messages,  # type: ignore
                temperature=temperature,
                max_retries=max_retries,
            )
            return result
        except Exception:
            # Fallback: JSON mode + manual Pydantic parse
            data = await self.complete_json(messages, model=model, temperature=temperature)
            return response_model.model_validate(data)

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        """Generate an embedding vector for text.

        Uses the OpenAI-compatible embeddings endpoint.
        Works with Ollama, OpenAI, vLLM, etc.

        Returns a list of floats (dimension depends on model).
        """
        embed_model = model or "default"
        try:
            response = await self._client.embeddings.create(
                input=text,
                model=embed_model,
            )
            return response.data[0].embedding
        except Exception:
            # If embeddings endpoint not available, return empty list
            # (concept still works, just without semantic search)
            return []


# Singleton
llm_router = LLMRouter()
