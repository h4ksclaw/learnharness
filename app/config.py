"""Application configuration — environment-driven."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://lh:lh_dev@localhost:5433/learnharness"

    # LLM (OpenAI-compatible — works with Ollama, vLLM, LM Studio, OpenAI, etc.)
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "llama3.2:3b"
    llm_api_key: str = "not-needed"

    # Server
    lh_host: str = "0.0.0.0"
    lh_port: int = 8000

    # Learning engine
    fsrs_target_retention: float = 0.9  # target recall probability
    bkt_prior: float = 0.5  # initial mastery estimate
    bkt_slip: float = 0.1  # P(wrong | known)
    bkt_guess: float = 0.25  # P(right | unknown)
    bkt_transit: float = 0.1  # P(learn per opportunity)

    # Proactive scheduling
    heartbeat_interval_minutes: int = 240  # check for due reviews every 4h

    model_config = {"env_file": ".env", "env_prefix": ""}


settings = Settings()
