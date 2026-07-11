"""Application configuration — environment-driven."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://lh:lh_dev@db:5432/learnharness"

    # LLM (OpenAI-compatible — works with Ollama, vLLM, OpenAI, etc.)
    llm_base_url: str = "http://ollama:11434/v1"
    llm_model: str = "qwen2.5:3b"
    llm_api_key: str = "not-needed"
    embedding_model: str = "nomic-embed-text"

    # Learning engine defaults
    fsrs_target_retention: float = 0.9
    bkt_prior: float = 0.5
    bkt_slip: float = 0.1
    bkt_guess: float = 0.25
    bkt_transit: float = 0.1

    # Worker
    heartbeat_interval_seconds: int = 300

    # Tools
    enable_web_search: bool = True
    enable_browser: bool = True

    model_config = {"env_prefix": "", "extra": "ignore"}


settings = Settings()
