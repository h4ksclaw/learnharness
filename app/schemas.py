"""Pydantic schemas for API request/response."""

from datetime import datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel
from pydantic import Field

# ─── Agent ───


class AgentCreate(BaseModel):
    name: str
    master_prompt: str
    tools: list[str] = Field(default_factory=lambda: ["web_search", "wikipedia"])
    channels: dict[str, Any] = Field(default_factory=dict)
    heartbeat_interval: int = 300


class AgentOut(BaseModel):
    id: str
    name: str
    master_prompt: str
    tools: list[str]
    channels: dict[str, Any]
    heartbeat_interval: int
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_agent(cls, agent: Any) -> "AgentOut":
        """Build AgentOut from an Agent model, masking sensitive channel fields."""
        masked_channels: dict[str, Any] = {}
        for platform, cfg in (agent.channels or {}).items():
            if isinstance(cfg, dict):
                masked = {**cfg}
                for key in ("token", "password", "api_key", "webhook_url"):
                    if key in masked:
                        masked[key] = "***"
                masked_channels[platform] = masked
            else:
                masked_channels[platform] = cfg
        return cls(
            id=agent.id,
            name=agent.name,
            master_prompt=agent.master_prompt,
            tools=agent.tools,
            channels=masked_channels,
            heartbeat_interval=agent.heartbeat_interval,
            active=agent.active,
            created_at=agent.created_at,
        )


# ─── Chat (OpenAI-compatible) ───


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    # LearnHarness extensions
    agent_id: str | None = None
    learner_id: str | None = None
    session_id: str | None = None


class Correction(BaseModel):
    original: str
    corrected: str
    rule: str = ""
    concept_id: str | None = None
    severity: Literal["error", "warning", "suggestion"] = "warning"


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
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


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


class CategoryProgress(BaseModel):
    category: str
    concept_count: int
    avg_mastery: float
    concepts: list[dict[str, Any]]


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
    rating: Literal[1, 2, 3, 4]


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


# ─── Categories ───


class CategoryCreate(BaseModel):
    name: str
    description: str = ""


class ConceptCreate(BaseModel):
    agent_id: str
    name: str
    category: str = "general"
    description: str = ""
    difficulty: float = 0.5


class ConceptOut(BaseModel):
    id: str
    name: str
    category: str
    description: str
    difficulty: float

    model_config = {"from_attributes": True}


# ─── Outbound ───


class OutboundMessageOut(BaseModel):
    id: int
    agent_id: str
    learner_id: str | None
    channel: str
    message: str
    extra: dict[str, Any] = Field(default_factory=dict)
    sent: bool
    created_at: datetime

    model_config = {"from_attributes": True}
