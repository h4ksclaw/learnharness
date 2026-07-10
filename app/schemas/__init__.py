"""Pydantic schemas for API request/response."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ─── Agent Personas ───

class AgentCreate(BaseModel):
    name: str
    domain: str
    description: str = ""
    response_language: str = "en"
    target_language: str | None = None
    level: str = "B1"
    system_prompt: str | None = None  # auto-generated if not provided
    rules: dict[str, Any] = Field(default_factory=dict)
    proactive: bool = True
    llm_model: str | None = None


class AgentOut(BaseModel):
    id: str
    name: str
    description: str
    domain: str
    response_language: str
    target_language: str | None
    level: str
    system_prompt: str
    rules: dict[str, Any]
    proactive: bool
    llm_model: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Chat (OpenAI-compatible) ───

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """OpenAI-compatible chat completions request + learning extensions."""
    # Standard OpenAI fields
    messages: list[ChatMessage]
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False

    # LearnHarness extensions (ignored by standard OpenAI clients)
    learner_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    analyze: bool = True  # whether to run learning analysis on this message


class Correction(BaseModel):
    original: str
    corrected: str
    rule: str = ""
    concept_id: str | None = None
    severity: Literal["error", "warning", "suggestion"] = "warning"
    expandable: bool = True


class MasteryDelta(BaseModel):
    concept_id: str
    concept_name: str
    before: float
    after: float
    direction: Literal["up", "down", "same"]


class ChatResponseChoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"


class ChatResponseUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatResponse(BaseModel):
    """OpenAI-compatible response + learning extensions."""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatResponseChoice]
    usage: ChatResponseUsage = Field(default_factory=ChatResponseUsage)

    # LearnHarness extensions
    corrections: list[Correction] = Field(default_factory=list)
    mastery_deltas: list[MasteryDelta] = Field(default_factory=list)
    concepts_detected: list[str] = Field(default_factory=list)
    reviews_due: list[dict[str, Any]] = Field(default_factory=list)


# ─── Mastery ───

class MasteryOut(BaseModel):
    concept_id: str
    concept_name: str
    category: str
    p_mastery: float
    interactions_count: int
    correct_count: int
    last_updated: datetime

    model_config = {"from_attributes": True}


class MasteryGraphOut(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


# ─── Reviews ───

class ReviewItemOut(BaseModel):
    id: int
    concept_id: str
    content: dict[str, Any]
    next_review: datetime
    reps: int
    lapses: int
    state: int

    model_config = {"from_attributes": True}


class ReviewAnswer(BaseModel):
    rating: Literal[1, 2, 3, 4]  # FSRS rating: again, hard, good, easy
    review_id: int


# ─── Learner ───

class LearnerCreate(BaseModel):
    agent_id: str
    name: str = "Learner"
    preferences: dict[str, Any] = Field(default_factory=dict)


class LearnerOut(BaseModel):
    id: str
    agent_id: str
    name: str
    overall_mastery: float
    created_at: datetime
    last_active: datetime | None

    model_config = {"from_attributes": True}
