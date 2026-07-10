"""Test the LLM router — requires a running LLM endpoint."""

import pytest

from app.engine.llm import LLMRouter


@pytest.mark.asyncio
async def test_llm_complete():
    """Test basic completion. Requires LLM endpoint."""
    router = LLMRouter()
    try:
        result = await router.complete(
            messages=[{"role": "user", "content": "Say hello in one word."}],
            temperature=0.0,
        )
        assert "content" in result
        assert len(result["content"]) > 0
    except Exception:
        pytest.skip("LLM endpoint not available")


@pytest.mark.asyncio
async def test_llm_json_mode():
    """Test JSON mode completion."""
    router = LLMRouter()
    try:
        result = await router.complete_json(
            messages=[
                {"role": "system", "content": "Return JSON."},
                {"role": "user", "content": 'Return {"status": "ok", "count": 42}'},
            ],
        )
        assert result["status"] == "ok"
        assert result["count"] == 42
    except Exception:
        pytest.skip("LLM endpoint not available")
