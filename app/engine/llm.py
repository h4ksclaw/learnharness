"""LLM Router — routes to any OpenAI-compatible endpoint.

Works with: Ollama, vLLM, LM Studio, OpenAI, DeepSeek, Gemini (via proxy),
OpenRouter, z.ai (GLM), Groq, any OpenAI-compatible API.

Provider detection:
    The router inspects ``LLM_BASE_URL`` to determine the provider and adjusts
    its behaviour accordingly:
    - z.ai / BigModel: ``response_format`` is sent only if the model supports
      JSON mode; otherwise the router falls back to text + regex extraction.
    - Ollama: ``response_format`` and ``max_tokens`` are always sent (Ollama
      ignores unknown fields gracefully).
    - OpenAI / Groq / OpenRouter: full OpenAI API surface is used.

Supports:
- Plain completions (httpx)
- JSON mode completions (with provider-aware fallback)
- Structured output via ``instructor`` (Pydantic models with auto-retry)
- Embedding generation
- Tool-calling (with provider-aware fallback)
"""

import json
import time
from typing import Any
from typing import TypeVar
from typing import cast

import httpx
import instructor
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel

from app.config import settings

T = TypeVar("T", bound=BaseModel)


# ─── Provider detection ────────────────────────────────────────────


def _detect_provider(base_url: str) -> str:
    """Return a provider tag from the base URL."""
    url = base_url.lower()
    if "z.ai" in url or "bigmodel" in url:
        return "zai"
    if "groq.com" in url:
        return "groq"
    if "openrouter.ai" in url:
        return "openrouter"
    if "deepseek.com" in url:
        return "deepseek"
    if "generativelanguage.googleapis.com" in url:
        return "gemini"
    if "ollama" in url or "11434" in url:
        return "ollama"
    if "api.openai.com" in url:
        return "openai"
    return "generic"


# Models known to support ``response_format: {"type": "json_object"}``.
# For providers like z.ai where support varies by model, we list the ones
# that are confirmed to work.  When a model is not in this set the router
# skips JSON mode and falls back to text extraction.
_ZAI_JSON_MODE_PREFIXES: tuple[str, ...] = (
    "glm-4",
    "glm-5",
)

_ZAI_JSON_MODE_EXCLUDED: frozenset[str] = frozenset(
    {
        # GLM-4.5-air and earlier low-tier models may not support JSON mode
        "glm-4.5-air",
    }
)


def _supports_json_mode(provider: str, model: str) -> bool:
    """Check if the provider+model combo supports ``response_format``."""
    if provider in ("ollama", "openai", "groq", "openrouter", "deepseek"):
        return True
    if provider == "zai":
        m = model.lower()
        if m in _ZAI_JSON_MODE_EXCLUDED:
            return False
        return any(m.startswith(p) for p in _ZAI_JSON_MODE_PREFIXES)
    # Unknown provider — try it; the fallback handles rejection
    return True


def _supports_tools(provider: str, model: str) -> bool:
    """Check if the provider+model combo supports tool/function calling."""
    if provider == "ollama":
        # Ollama supports tools for most models
        return True
    if provider == "zai":
        m = model.lower()
        # GLM-4.5+ supports function calling; older models may not
        return any(m.startswith(p) for p in ("glm-4", "glm-5"))
    return True


# ─── LLMRouter ─────────────────────────────────────────────────────


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
        self.provider = _detect_provider(self.base_url)

        # OpenAI client for instructor and embeddings
        self._client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key if self.api_key != "not-needed" else "ollama",
        )
        # instructor-wrapped client for structured output
        self._structured = instructor.from_openai(self._client)

    # ─── Headers ────────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        """Build auth headers for httpx calls."""
        headers = {"Content-Type": "application/json"}
        if self.api_key and self.api_key != "not-needed":
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    # ─── Plain completions ──────────────────────────────────────────

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

        # Provider-aware: skip response_format if the model doesn't support it
        if response_format and not _supports_json_mode(self.provider, model):
            response_format = None

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
                headers=self._headers(),
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

    # ─── JSON completions ───────────────────────────────────────────

    async def complete_json(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        """Call the LLM with JSON mode and parse the response.

        Falls back to extracting JSON from text if response_format isn't
        supported or the provider rejects it.
        """
        model = model or self.default_model
        use_json_mode = _supports_json_mode(self.provider, model)

        try:
            result = await self.complete(
                messages,
                model=model,
                temperature=temperature,
                response_format={"type": "json_object"} if use_json_mode else None,
            )
            parsed: dict[str, Any] = json.loads(result["content"])
            return parsed
        except (json.JSONDecodeError, httpx.HTTPStatusError):
            # Fallback: try without response_format, extract JSON from text
            result = await self.complete(messages, model=model, temperature=temperature)
            content = result["content"]
            try:
                parsed = json.loads(content)
                return parsed
            except json.JSONDecodeError:
                # Last resort: find first { and last }
                start_idx = content.find("{")
                end_idx = content.rfind("}")
                if start_idx >= 0 and end_idx > start_idx:
                    parsed = json.loads(content[start_idx : end_idx + 1])
                    return parsed
                raise ValueError(
                    f"Could not parse JSON from LLM response: {content[:200]}"
                ) from None

    # ─── Structured output (instructor) ─────────────────────────────

    async def complete_structured(
        self,
        response_model: type[T],
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.3,
        max_retries: int = 2,
    ) -> T:
        """Call the LLM with instructor for guaranteed structured output.

        Falls back to complete_json + manual parse if instructor fails.
        """
        try:
            result = await self._structured.chat.completions.create(
                model=model or self.default_model,
                response_model=response_model,
                messages=cast(list[ChatCompletionMessageParam], messages),
                temperature=temperature,
                max_retries=max_retries,
            )
            return cast("T", result)
        except Exception:
            # Fallback: JSON mode + manual Pydantic parse
            data = await self.complete_json(messages, model=model, temperature=temperature)
            return response_model.model_validate(data)

    # ─── Tool-calling ───────────────────────────────────────────────

    async def complete_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        max_rounds: int = 5,
    ) -> dict[str, Any]:
        """Call the LLM with tool-calling support.

        Handles the tool-call loop: sends the request, detects tool_calls in the
        response, and returns them. The caller is responsible for executing the
        tools and re-calling with the results appended to the messages.

        Args:
            messages: Chat messages including any prior tool results.
            tools: OpenAI-format tool schemas.
            model: Override model name.
            temperature: Sampling temperature.
            max_tokens: Max response tokens.
            max_rounds: Not used here — caller controls the loop.

        Returns:
            dict with content, tool_calls, model, usage, latency_ms
        """
        model = model or self.default_model

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if _supports_tools(self.provider, model):
            payload["tools"] = tools
        if max_tokens:
            payload["max_tokens"] = max_tokens

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()

        latency_ms = int((time.monotonic() - start) * 1000)
        msg = data["choices"][0]["message"]

        return {
            "content": msg.get("content"),
            "tool_calls": msg.get("tool_calls"),
            "model": data.get("model", model),
            "usage": data.get("usage", {}),
            "latency_ms": latency_ms,
        }

    # ─── Embeddings ─────────────────────────────────────────────────

    async def embed(self, text: str, model: str | None = None) -> list[float] | None:
        """Generate an embedding vector for text."""
        embed_model = model or settings.embedding_model
        try:
            response = await self._client.embeddings.create(
                input=text,
                model=embed_model,
            )
            return list(response.data[0].embedding)
        except Exception:
            return None


# Singleton
llm_router = LLMRouter()
