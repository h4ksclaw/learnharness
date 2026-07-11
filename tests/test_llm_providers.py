"""Tests for LLM provider detection and compatibility."""

from app.engine.llm import _detect_provider
from app.engine.llm import _supports_json_mode
from app.engine.llm import _supports_tools


class TestProviderDetection:
    def test_ollama_detection(self):
        assert _detect_provider("http://ollama:11434/v1") == "ollama"
        assert _detect_provider("http://localhost:11434/v1") == "ollama"

    def test_zai_detection(self):
        assert _detect_provider("https://api.z.ai/api/paas/v4") == "zai"
        assert _detect_provider("https://open.bigmodel.cn/api/paas/v4") == "zai"

    def test_openai_detection(self):
        assert _detect_provider("https://api.openai.com/v1") == "openai"

    def test_groq_detection(self):
        assert _detect_provider("https://api.groq.com/openai/v1") == "groq"

    def test_openrouter_detection(self):
        assert _detect_provider("https://openrouter.ai/api/v1") == "openrouter"

    def test_deepseek_detection(self):
        assert _detect_provider("https://api.deepseek.com/v1") == "deepseek"

    def test_gemini_detection(self):
        assert (
            _detect_provider("https://generativelanguage.googleapis.com/v1beta/openai/") == "gemini"
        )

    def test_generic_detection(self):
        assert _detect_provider("https://my-custom-llm.example.com/v1") == "generic"


class TestJsonModeSupport:
    def test_ollama_always_supports_json(self):
        assert _supports_json_mode("ollama", "qwen2.5:3b")
        assert _supports_json_mode("ollama", "llama3")
        assert _supports_json_mode("ollama", "anything")

    def test_openai_always_supports_json(self):
        assert _supports_json_mode("openai", "gpt-4o")
        assert _supports_json_mode("openai", "gpt-3.5-turbo")

    def test_zai_glm4_supports_json(self):
        assert _supports_json_mode("zai", "glm-4.5")
        assert _supports_json_mode("zai", "glm-4.6")
        assert _supports_json_mode("zai", "glm-4.7")

    def test_zai_glm5_supports_json(self):
        assert _supports_json_mode("zai", "glm-5")
        assert _supports_json_mode("zai", "glm-5.1")
        assert _supports_json_mode("zai", "glm-5.2")

    def test_zai_air_excluded(self):
        assert not _supports_json_mode("zai", "glm-4.5-air")

    def test_generic_tries_json(self):
        assert _supports_json_mode("generic", "unknown-model")


class TestToolSupport:
    def test_ollama_supports_tools(self):
        assert _supports_tools("ollama", "qwen2.5:3b")

    def test_zai_glm4_supports_tools(self):
        assert _supports_tools("zai", "glm-4.5")
        assert _supports_tools("zai", "glm-5.2")

    def test_generic_supports_tools(self):
        assert _supports_tools("generic", "unknown-model")
