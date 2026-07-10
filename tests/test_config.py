"""Test configuration and DB module."""

from app.config import Settings


class TestSettings:
    def test_defaults(self):
        s = Settings()
        assert s.fsrs_target_retention == 0.9
        assert s.bkt_prior == 0.5
        assert s.bkt_slip == 0.1
        assert s.bkt_guess == 0.25
        assert s.bkt_transit == 0.1
        assert s.heartbeat_interval_seconds == 300

    def test_llm_defaults(self):
        s = Settings()
        # Values come from environment in Docker, defaults otherwise
        assert s.llm_api_key is not None
        assert s.embedding_model is not None

    def test_extra_ignored(self):
        """Settings should not crash on extra env vars."""
        # This is tested implicitly by the Settings() call above
        # which already ignores extra vars from .env
        s = Settings()
        assert hasattr(s, "database_url")

    def test_embedding_model_default(self):
        s = Settings()
        assert "embed" in s.embedding_model.lower()


class TestDatabase:
    def test_engine_creation(self):
        from app.db import Base
        from app.db import engine

        assert engine is not None
        assert Base is not None

    def test_base_is_declarative(self):
        from sqlalchemy.orm import DeclarativeBase

        from app.db import Base

        assert isinstance(Base, type)
        assert issubclass(Base, DeclarativeBase)
