"""ORM models — the complete schema for a domain-agnostic learning harness."""

from datetime import datetime, timezone
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Agent(Base):
    """A tutor persona — defines what the agent teaches, how it behaves, language constraints."""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    # The domain this agent covers, e.g. "German", "Python", "Organic Chemistry"
    domain: Mapped[str] = mapped_column(String(100))
    # Language the AGENT speaks to the user in
    response_language: Mapped[str] = mapped_column(String(50), default="en")
    # Language the USER is expected to use (the target language for lang learning)
    target_language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # CEFR level or difficulty target
    level: Mapped[str] = mapped_column(String(10), default="B1")
    # Full system prompt persona — the core instruction set
    system_prompt: Mapped[str] = mapped_column(Text)
    # Additional rules as structured data
    rules: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Whether the agent proactively initiates contact
    proactive: Mapped[bool] = mapped_column(Boolean, default=True)
    # LLM model override (per-agent)
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    learners: Mapped[list["Learner"]] = relationship(back_populates="agent")


class Learner(Base):
    """A user profile — tracks overall progress and preferences."""

    __tablename__ = "learners"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
    name: Mapped[str] = mapped_column(String(200), default="Learner")
    # General proficiency estimate across all concepts
    overall_mastery: Mapped[float] = mapped_column(Float, default=0.0)
    # Learner preferences
    preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_active: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    agent: Mapped[Agent] = relationship(back_populates="learners")
    mastery_records: Mapped[list["Mastery"]] = relationship(back_populates="learner", cascade="all, delete-orphan")
    reviews: Mapped[list["ReviewItem"]] = relationship(back_populates="learner", cascade="all, delete-orphan")


class Concept(Base):
    """A knowledge graph node — a concept, skill, or fact within a domain.

    Concepts are created dynamically by the LLM as it analyzes conversation.
    The embedding allows semantic search over the concept space.
    """

    __tablename__ = "concepts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    # Human-readable name, e.g. "ser vs estar", "list comprehension", "SN2 reaction"
    name: Mapped[str] = mapped_column(String(300))
    # Domain tag for grouping, e.g. "grammar", "syntax", "vocabulary"
    category: Mapped[str] = mapped_column(String(100), default="general")
    description: Mapped[str] = mapped_column(Text, default="")
    # Difficulty estimate 0-1 (set by LLM or heuristic)
    difficulty: Mapped[float] = mapped_column(Float, default=0.5)
    # Semantic embedding for vector search (1536 dims for OpenAI, configurable)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    edges_from: Mapped[list["ConceptEdge"]] = relationship(
        foreign_keys="ConceptEdge.target_id", back_populates="target"
    )
    edges_to: Mapped[list["ConceptEdge"]] = relationship(
        foreign_keys="ConceptEdge.source_id", back_populates="source"
    )


class ConceptEdge(Base):
    """A relationship between concepts — prerequisite, related, part_of, etc.

    This is what makes it a graph, not just a list.
    The LLM identifies these when constructing the knowledge graph.
    """

    __tablename__ = "concept_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("concepts.id"), index=True)
    target_id: Mapped[str] = mapped_column(ForeignKey("concepts.id"), index=True)
    # prerequisite: must know source before target
    # related: concepts that reinforce each other
    # part_of: source is a subtopic of target
    # contrasts_with: commonly confused concepts
    edge_type: Mapped[str] = mapped_column(String(50), default="related")
    weight: Mapped[float] = mapped_column(Float, default=1.0)

    source: Mapped[Concept] = relationship(foreign_keys=[source_id], back_populates="edges_to")
    target: Mapped[Concept] = relationship(foreign_keys=[target_id], back_populates="edges_from")


class Mastery(Base):
    """Per-concept mastery state for a learner — updated by BKT after each interaction.

    p_mastery is the probability (0-1) that the learner has mastered this concept.
    This is the output of Bayesian Knowledge Tracing.
    """

    __tablename__ = "mastery"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id"), index=True)
    concept_id: Mapped[str] = mapped_column(ForeignKey("concepts.id"), index=True)
    # BKT state
    p_mastery: Mapped[float] = mapped_column(Float, default=0.5)
    p_transit: Mapped[float] = mapped_column(Float, default=0.1)
    p_slip: Mapped[float] = mapped_column(Float, default=0.1)
    p_guess: Mapped[float] = mapped_column(Float, default=0.25)
    # Tracking
    interactions_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    learner: Mapped[Learner] = relationship(back_populates="mastery_records")


class ReviewItem(Base):
    """An FSRS-managed review item — a flashcard, concept prompt, or practice task.

    The FSRS algorithm determines when to surface this to the learner next.
    """

    __tablename__ = "review_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id"), index=True)
    concept_id: Mapped[str] = mapped_column(ForeignKey("concepts.id"), index=True)
    # The review content (flexible — can be a flashcard, a prompt, an exercise)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # FSRS scheduling state
    stability: Mapped[float] = mapped_column(Float, default=0.0)
    difficulty: Mapped[float] = mapped_column(Float, default=0.0)
    elapsed_days: Mapped[float] = mapped_column(Float, default=0.0)
    scheduled_days: Mapped[float] = mapped_column(Float, default=0.0)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[int] = mapped_column(Integer, default=0)  # 0=new, 1=learning, 2=review, 3=relearning
    last_review: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    learner: Mapped[Learner] = relationship(back_populates="reviews")


class Interaction(Base):
    """A single interaction — a chat message, quiz answer, or flashcard review.

    This is the event log. Every time the learner does something, it's recorded here.
    The knowledge tracing engine reads from this to update mastery.
    """

    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id"), index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    # Type: "chat", "quiz", "flashcard", "correction"
    type: Mapped[str] = mapped_column(String(30), default="chat")
    # The user's input
    user_input: Mapped[str] = mapped_column(Text)
    # The agent's response
    agent_response: Mapped[str] = mapped_column(Text, default="")
    # Whether the interaction showed mastery (null for free chat, bool for quizzes)
    correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Which concepts were involved (for mastery updates)
    concept_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    # Corrections made during this interaction
    corrections: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    # Mastery state snapshot before/after
    mastery_deltas: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ErrorPattern(Base):
    """Tracks recurring errors — helps the system identify weak spots and schedule targeted reviews."""

    __tablename__ = "error_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id"), index=True)
    concept_id: Mapped[str] = mapped_column(ForeignKey("concepts.id"), index=True)
    error_type: Mapped[str] = mapped_column(String(100))
    count: Mapped[int] = mapped_column(Integer, default=1)
    examples: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
