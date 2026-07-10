# LearnHarness — Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend Layer                           │
│                                                                  │
│  Web UI (Next.js)    IRC Bot    Telegram Bot    Flutter App     │
│  management + chat   text-only   inline btns    mobile push     │
└──────────────┬───────────────────────────────────────────────────┘
               │ HTTP / SSE / WebSocket
┌──────────────▼───────────────────────────────────────────────────┐
│                      FastAPI Backend                             │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │                    API Layer                              │     │
│  │                                                           │     │
│  │  POST /v1/chat/completions  (OpenAI-compatible)          │     │
│  │  GET/POST /v1/agents        (persona CRUD)               │     │
│  │  GET /v1/mastery/{id}       (knowledge state)            │     │
│  │  GET /v1/reviews/{id}       (FSRS due items)            │     │
│  │  GET /v1/heartbeat          (proactive actions)          │     │
│  └─────────────────────────────────────────────────────────┘     │
│                              │                                   │
│  ┌───────────────────────────▼──────────────────────────────┐    │
│  │                   Agent Harness                           │    │
│  │                                                           │    │
│  │  1. Analyze message (KG engine)                          │    │
│  │  2. Update knowledge graph + mastery (BKT)                │    │
│  │  3. Build enriched system prompt (persona + context)     │    │
│  │  4. Forward to LLM (any provider)                        │    │
│  │  5. Return response + corrections + deltas               │    │
│  └───────────────────────────┬──────────────────────────────┘    │
│                              │                                   │
│  ┌───────────┬───────────────┼───────────────┬─────────────────┐ │
│  │  KG       │  BKT          │  FSRS         │  Scheduler      │ │
│  │  Engine   │  Tracer       │  Scheduler    │  (Heartbeat)    │ │
│  │           │               │               │                 │ │
│  │  concept  │  mastery      │  review       │  due reviews    │ │
│  │  extract  │  prob update  │  scheduling   │  inactive       │ │
│  │  graph    │  per concept  │  interval     │  checkins       │ │
│  │  query    │  0-1          │  calc         │  weak spots     │ │
│  └───────────┴───────────────┴───────────────┴─────────────────┘ │
│                              │                                   │
│  ┌───────────────────────────▼──────────────────────────────┐    │
│  │                    LLM Router                             │    │
│  │                                                           │    │
│  │  Ollama (local)  OpenAI  DeepSeek  vLLM  OpenRouter      │    │
│  │  LM Studio  Gemini  Any OpenAI-compatible endpoint       │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│                    PostgreSQL + pgvector                          │
│                                                                  │
│  agents          learner profiles + system prompts              │
│  learners        user state                                      │
│  concepts        KG nodes (name, category, difficulty, embedding)│
│  concept_edges   KG edges (prerequisite, related, contrasts)     │
│  mastery         per-concept BKT state per learner               │
│  review_items    FSRS scheduling state per concept per learner   │
│  interactions    full chat/quiz/flashcard event log              │
│  error_patterns  recurring mistakes per concept                  │
└──────────────────────────────────────────────────────────────────┘
```

## Data Model

### Core Tables

```
agents
├── id, name, domain, description
├── response_language, target_language, level
├── system_prompt (the "master prompt" — auto-generated or custom)
├── rules (JSONB — template type, extra rules)
├── proactive (bool — should this agent reach out?)
└── llm_model (optional per-agent model override)

learners
├── id, agent_id, name
├── overall_mastery (aggregate estimate)
├── preferences (JSONB)
└── last_active

concepts (knowledge graph nodes)
├── id, agent_id
├── name (e.g. "ser vs estar", "list comprehension")
├── category (e.g. "grammar", "syntax", "vocabulary")
├── description
├── difficulty (0-1)
└── embedding (Vector(1536) for semantic search)

concept_edges (knowledge graph relationships)
├── source_id → target_id
├── edge_type: prerequisite | related | part_of | contrasts_with
└── weight

mastery (BKT state — per learner per concept)
├── learner_id, concept_id
├── p_mastery (0-1 probability the learner has mastered this)
├── p_transit, p_slip, p_guess (BKT parameters)
├── interactions_count, correct_count
└── last_updated

review_items (FSRS scheduling state)
├── learner_id, concept_id
├── content (JSONB — flashcard front/back, exercise, etc.)
├── stability, difficulty (FSRS memory model)
├── reps, lapses, state
├── last_review, next_review
└── elapsed_days, scheduled_days

interactions (event log)
├── learner_id, agent_id, session_id
├── type: chat | quiz | flashcard | correction
├── user_input, agent_response
├── correct (null for chat, bool for quizzes)
├── concept_ids[] (which concepts were involved)
├── corrections[] (structured error data)
└── mastery_deltas (before/after snapshot)

error_patterns
├── learner_id, concept_id
├── error_type (the rule violated)
├── count, examples[]
└── last_seen
```

## Chat Pipeline

Every message goes through this pipeline:

```
User sends message to POST /v1/chat/completions
         │
         ▼
    ┌─────────────────────────────────────┐
    │ 1. CONCEPT EXTRACTION               │
    │    LLM analyzes user message        │
    │    Output: {concepts, edges,        │
    │    corrections, mastery_signals,    │
    │    needs_review}                    │
    └──────────────┬──────────────────────┘
                   │
    ┌──────────────▼──────────────────────┐
    │ 2. KNOWLEDGE GRAPH UPDATE           │
    │    Upsert concepts into DB          │
    │    Add edges (prerequisites etc.)   │
    │    Record error patterns            │
    └──────────────┬──────────────────────┘
                   │
    ┌──────────────▼──────────────────────┐
    │ 3. MASTERY UPDATE (BKT)             │
    │    For each concept detected:       │
    │    Update P(mastery) using BKT      │
    │    with soft inference from LLM     │
    │    confidence signal                │
    └──────────────┬──────────────────────┘
                   │
    ┌──────────────▼──────────────────────┐
    │ 4. CONTEXT BUILDING                 │
    │    Query learner's current state:   │
    │    - Weak areas (< 0.5 mastery)     │
    │    - Mastered concepts (> 0.8)      │
    │    - Due reviews                    │
    │    Inject into system prompt        │
    └──────────────┬──────────────────────┘
                   │
    ┌──────────────▼──────────────────────┐
    │ 5. LLM CALL                         │
    │    Enhanced system prompt +         │
    │    conversation history → LLM       │
    │    (any OpenAI-compatible provider) │
    └──────────────┬──────────────────────┘
                   │
    ┌──────────────▼──────────────────────┐
    │ 6. RESPONSE ASSEMBLY                │
    │    OpenAI-shaped response +         │
    │    corrections[]                    │
    │    mastery_deltas[]                 │
    │    concepts_detected[]              │
    │    reviews_due[]                    │
    └──────────────┬──────────────────────┘
                   │
    ┌──────────────▼──────────────────────┐
    │ 7. PERSIST + RETURN                 │
    │    Save interaction to DB           │
    │    Update learner.last_active       │
    │    Return to client                 │
    └─────────────────────────────────────┘
```

## Frontend Protocol

The API returns a standard OpenAI response with optional extension fields:

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "model": "llama3.2:3b",
  "choices": [{
    "message": {"role": "assistant", "content": "Das ist richtig! ..."},
    "finish_reason": "stop"
  }],

  // ── LearnHarness extensions (ignored by standard clients) ──
  "corrections": [{
    "original": "ich bin müde",
    "corrected": "ich habe mühe",
    "rule": "Use 'haben' with 'Mühe'",
    "concept_id": "haben_vs_sein",
    "severity": "warning",
    "expandable": true
  }],
  "mastery_deltas": [{
    "concept": "haben_vs_sein",
    "before": 0.52,
    "after": 0.43,
    "direction": "down"
  }],
  "concepts_detected": ["haben_vs_sein", "adjective_endings"],
  "reviews_due": [{"id": 42, "concept_id": "...", "next_review": "..."}]
}
```

| Frontend | How It Renders |
|----------|---------------|
| **Web UI** | Corrections as inline expandable overlays, mastery deltas as badges, reviews as toasts |
| **IRC bot** | Flatten to text: `"⚠️ Correction: use 'haben' with 'Mühe'"` |
| **Telegram** | Inline keyboard buttons: `[Expand correction]` `[Show progress]` |
| **Standard OpenAI client** | Just sees the text response — learning logic runs silently |

## Proactive Scheduler (Heartbeat)

The scheduler runs on a configurable interval and checks each learner:

```
Every 4 hours:
  For each learner with proactive agent:
    1. Are FSRS reviews due? → "You have 3 reviews waiting"
    2. Inactive > 24h? → "Want to practice some German?"
    3. Weakest concept < 0.3? → "Let's work on adjective endings"

  Emit HeartbeatResult → frontend delivers via its channel
  (IRC PRIVMSG, Telegram push, web notification)
```

## File Structure

```
learnharness/
├── app/
│   ├── main.py              # FastAPI app, lifespan, router registration
│   ├── config.py            # Environment-driven settings
│   ├── db.py                # Async SQLAlchemy session
│   ├── models/
│   │   └── __init__.py      # All ORM models (7 tables)
│   ├── schemas/
│   │   └── __init__.py      # Pydantic request/response models
│   ├── routers/
│   │   ├── chat.py          # POST /v1/chat/completions
│   │   ├── agents.py        # Agent + Learner CRUD
│   │   ├── mastery.py       # Knowledge state + graph queries
│   │   ├── reviews.py       # FSRS review management
│   │   └── heartbeat.py     # Proactive scheduler endpoints
│   ├── engine/
│   │   ├── llm.py           # OpenAI-compatible LLM router
│   │   ├── fsrs_sched.py    # FSRS spaced repetition
│   │   ├── knowledge_tracing.py  # BKT mastery estimation
│   │   └── knowledge_graph.py    # LLM concept extraction + graph mgmt
│   └── agents/
│       ├── persona.py       # Agent persona templates + builder
│       ├── harness.py       # Main chat processing pipeline
│       └── scheduler.py     # Proactive heartbeat
├── tests/
│   ├── test_knowledge_tracing.py
│   ├── test_fsrs.py
│   ├── test_persona.py
│   ├── test_llm.py
│   └── test_api.py
├── docs/
│   ├── VISION.md            # Vision + design decisions
│   └── ARCHITECTURE.md      # This file
├── compose.yaml             # Postgres+pgvector + API
├── Dockerfile
├── pyproject.toml
└── README.md
```
