"""ORM models — generic domain-agnostic learning harness.

Core entities:
  Agent    — a tutor with a master prompt, tools, and channels
  Learner  — a user being taught by an agent
  Concept  — knowledge graph node (auto-extracted from conversation)
  Mastery  — per-concept BKT state per learner
  Review   — FSRS-scheduled review item
  Interaction — event log of everything that happened
"""

from datetime import UTC
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Agent(Base):
    """A tutor agent — defined entirely by its master prompt.

    No hardcoded domain or language. The master prompt IS the configuration.
    The agent can have tools (web_search, browser, arxiv, wikipedia) and
    channels (irc, telegram, web) for communication.

    Examples:
      - "You are a German tutor. Only respond in German..."
      - "You are a Python mentor. Use Socratic method..."
      - "You are a history teacher focusing on WWII..."
    """

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    master_prompt: Mapped[str] = mapped_column(Text)
    # Tools the agent can use: ["web_search", "browser", "arxiv", "wikipedia"]
    tools: Mapped[list[str]] = mapped_column(JSONB, default=list)
    # Channel config: {"irc": {"host": "...", "channel": "..."}, "telegram": {"token": "..."}}
    channels: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # How often to initiate contact (seconds). 0 = never.
    heartbeat_interval: Mapped[int] = mapped_column(Integer, default=300)
    # Per-agent LLM override
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Active toggle
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    learners: Mapped[list["Learner"]] = relationship(back_populates="agent")


class Learner(Base):
    """A user profile."""

    __tablename__ = "learners"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
    name: Mapped[str] = mapped_column(String(200), default="Learner")
    overall_mastery: Mapped[float] = mapped_column(Float, default=0.0)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_active: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    agent: Mapped[Agent] = relationship(back_populates="learners")
    mastery_records: Mapped[list["Mastery"]] = relationship(
        back_populates="learner", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["ReviewItem"]] = relationship(
        back_populates="learner", cascade="all, delete-orphan"
    )


class Concept(Base):
    """A knowledge graph node — a concept, skill, or fact.

    Auto-created by the LLM as it analyzes conversation.
    The embedding enables semantic search over the concept space.
    """

    __tablename__ = "concepts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    name: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(100), default="general")
    description: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[float] = mapped_column(Float, default=0.5)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ConceptEdge(Base):
    """A relationship between concepts."""

    __tablename__ = "concept_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("concepts.id"), index=True)
    target_id: Mapped[str] = mapped_column(ForeignKey("concepts.id"), index=True)
    # prerequisite, related, part_of, contrasts_with
    edge_type: Mapped[str] = mapped_column(String(50), default="related")
    weight: Mapped[float] = mapped_column(Float, default=1.0)


class Mastery(Base):
    """Per-concept mastery state — updated by BKT after each interaction."""

    __tablename__ = "mastery"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id"), index=True)
    concept_id: Mapped[str] = mapped_column(ForeignKey("concepts.id"), index=True)
    p_mastery: Mapped[float] = mapped_column(Float, default=0.5)
    p_transit: Mapped[float] = mapped_column(Float, default=0.1)
    p_slip: Mapped[float] = mapped_column(Float, default=0.1)
    p_guess: Mapped[float] = mapped_column(Float, default=0.25)
    interactions_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    learner: Mapped[Learner] = relationship(back_populates="mastery_records")


class ReviewItem(Base):
    """FSRS-scheduled review item."""

    __tablename__ = "review_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id"), index=True)
    concept_id: Mapped[str] = mapped_column(ForeignKey("concepts.id"), index=True)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    stability: Mapped[float] = mapped_column(Float, default=0.0)
    difficulty: Mapped[float] = mapped_column(Float, default=0.0)
    elapsed_days: Mapped[float] = mapped_column(Float, default=0.0)
    scheduled_days: Mapped[float] = mapped_column(Float, default=0.0)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[int] = mapped_column(Integer, default=1)  # 1=learning, 2=review, 3=relearning
    last_review: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    learner: Mapped[Learner] = relationship(back_populates="reviews")


class Interaction(Base):
    """Event log — every message, quiz, flashcard, correction."""

    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id"), index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    # chat, quiz, flashcard, correction, heartbeat, tool_result
    type: Mapped[str] = mapped_column(String(30), default="chat")
    user_input: Mapped[str] = mapped_column(Text, default="")
    agent_response: Mapped[str] = mapped_column(Text, default="")
    correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    concept_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    corrections: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    mastery_deltas: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Tool calls made during this interaction
    tool_calls: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ErrorPattern(Base):
    """Recurring errors — for targeted review scheduling."""

    __tablename__ = "error_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id"), index=True)
    concept_id: Mapped[str] = mapped_column(ForeignKey("concepts.id"), index=True)
    error_type: Mapped[str] = mapped_column(String(100))
    count: Mapped[int] = mapped_column(Integer, default=1)
    examples: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OutboundMessage(Base):
    """Messages the agent wants to send to a channel (heartbeat, proactime, etc).

    The worker creates these, and channel adapters pick them up.
    """

    __tablename__ = "outbound_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    learner_id: Mapped[str | None] = mapped_column(ForeignKey("learners.id"), nullable=True)
    channel: Mapped[str] = mapped_column(String(50))  # irc, telegram, web, all
    message: Mapped[str] = mapped_column(Text)
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def register_all_models() -> None:
    """Import all models so they register with Base.metadata.

    Call this from alembic/env.py, init_db.py, and app/main.py
    instead of duplicating the import block in each file.
    """
    # Import here to ensure all models are loaded into Base.metadata
    from app.models import Agent  # noqa: F401
    from app.models import Concept  # noqa: F401
    from app.models import ConceptEdge  # noqa: F401
    from app.models import ErrorPattern  # noqa: F401
    from app.models import Interaction  # noqa: F401
    from app.models import Learner  # noqa: F401
    from app.models import Mastery  # noqa: F401
    from app.models import OutboundMessage  # noqa: F401
    from app.models import ReviewItem  # noqa: F401
