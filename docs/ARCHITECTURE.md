# LearnHarness — Architecture

## System Overview

```mermaid
graph TB
    subgraph Frontend["Frontend Layer"]
        Web["Web UI<br/>management + chat"]
        IRC["IRC Bot<br/>text-only"]
        TG["Telegram Bot<br/>inline buttons"]
        DC["Discord Bot"]
        CLI["CLI / curl<br/>any OpenAI client"]
    end

    Frontend -- "HTTP" --> API

    subgraph Backend["FastAPI Backend"]
        API["POST /v1/chat/completions<br/>GET/POST /v1/agents<br/>GET /v1/mastery · /v1/reviews<br/>GET /v1/outbound"]

        subgraph Harness["Agent Harness"]
            H["1. Analyze message (KG engine)<br/>2. Update knowledge graph + mastery (BKT)<br/>3. Build enriched system prompt<br/>4. Forward to LLM with tools<br/>5. Return response + corrections + deltas"]
        end

        subgraph Engines["Learning Engines"]
            KG["KG Engine<br/>Concept extraction<br/>Graph building"]
            BKT["BKT Tracer<br/>Mastery probability<br/>Per concept"]
            FSRS["FSRS Scheduler<br/>Review scheduling<br/>Interval calculation"]
            SCHED["Scheduler<br/>Due reviews<br/>Inactive checkins<br/>Weak spot focus"]
        end

        CHAN["Channel Manager<br/>IRC · Telegram · Discord<br/>Access control + routing"]
        LLM["LLM Router<br/>Ollama · OpenAI · vLLM · z.ai<br/>Any OpenAI-compatible"]
    end

    subgraph Data["PostgreSQL + pgvector"]
        T1["agents — master prompts + config"]
        T2["learners — user state"]
        T3["concepts — KG nodes + embeddings"]
        T4["concept_edges — KG relationships"]
        T5["mastery — per-concept BKT state"]
        T6["review_items — FSRS scheduling"]
        T7["interactions — event log"]
        T8["error_patterns — recurring mistakes"]
        T9["outbound_messages — proactive queue"]
    end

    API --> Harness
    H --> KG
    H --> BKT
    H --> FSRS
    H --> LLM
    SCHED --> FSRS
    CHAN --> API
    KG --> Data
    BKT --> Data
    FSRS --> Data

    style Frontend fill:#1a1a2e,stroke:#4EC9B0,color:#4EC9B0
    style Backend fill:#1a1a2e,stroke:#569CD6,color:#569CD6
    style Data fill:#1a1a2e,stroke:#C586C0,color:#C586C0
```

## Data Model

```mermaid
erDiagram
    agents ||--o{ learners : "has"
    agents ||--o{ concepts : "owns"
    agents ||--o{ interactions : "logs"
    agents ||--o{ outbound_messages : "sends"
    learners ||--o{ mastery : "tracks"
    learners ||--o{ review_items : "reviews"
    learners ||--o{ interactions : "has"
    learners ||--o{ error_patterns : "has"
    concepts ||--o{ concept_edges : "source"
    concepts ||--o{ concept_edges : "target"
    concepts ||--o{ mastery : "assessed by"
    concepts ||--o{ review_items : "tested by"
    concepts ||--o{ error_patterns : "has"

    agents {
        string id PK
        string name
        text master_prompt
        jsonb tools
        jsonb channels
        int heartbeat_interval
        string llm_model
        bool active
    }

    learners {
        string id PK
        string agent_id FK
        string name
        float overall_mastery
        jsonb preferences
        datetime last_active
    }

    concepts {
        string id PK
        string agent_id FK
        string name
        string category
        text description
        float difficulty
        vector embedding
    }

    mastery {
        int id PK
        string learner_id FK
        string concept_id FK
        float p_mastery
        float p_transit
        float p_slip
        float p_guess
        int interactions_count
        int correct_count
    }

    review_items {
        int id PK
        string learner_id FK
        string concept_id FK
        jsonb content
        float stability
        float difficulty
        int reps
        int lapses
        int state
        datetime next_review
    }
```

## Chat Pipeline

Every message goes through this pipeline:

```mermaid
flowchart TD
    START([User sends message]) --> P1

    P1["① CONCEPT EXTRACTION<br/>LLM analyzes user message<br/>→ concepts, edges, corrections, mastery signals"]
    P1 --> P2

    P2["② KNOWLEDGE GRAPH UPDATE<br/>Upsert concepts into DB<br/>Add prerequisite edges<br/>Record error patterns"]
    P2 --> P3

    P3["③ MASTERY UPDATE — BKT<br/>For each concept detected:<br/>Update P(mastery) using BKT<br/>with soft inference from LLM confidence"]
    P3 --> P4

    P4["④ CONTEXT BUILDING<br/>Query learner's current state:<br/>Weak areas < 50%<br/>Mastered concepts > 80%<br/>Inject into system prompt"]
    P4 --> P5

    P5{"Agent has<br/>tools?"}
    P5 -- Yes --> P5A["⑤ LLM CALL WITH TOOLS<br/>Enhanced prompt + history<br/>LLM may call: web_search, wikipedia, arxiv<br/>Tool results fed back to LLM"]
    P5 -- No --> P5B["⑤ LLM CALL<br/>Enhanced prompt + history<br/>→ LLM generates response"]
    P5A --> P6
    P5B --> P6

    P6["⑥ RESPONSE ASSEMBLY<br/>OpenAI-shaped response +<br/>corrections, mastery_deltas,<br/>concepts_detected, reviews_due"]
    P6 --> P7

    P7([⑦ PERSIST + RETURN<br/>Save interaction to DB<br/>Update learner.last_active])

    style P1 fill:#4EC9B0,stroke:none,color:#000
    style P2 fill:#C586C0,stroke:none,color:#000
    style P3 fill:#569CD6,stroke:none,color:#000
    style P4 fill:#CE9178,stroke:none,color:#000
    style P5A fill:#6A9955,stroke:none,color:#000
    style P5B fill:#6A9955,stroke:none,color:#000
    style P6 fill:#DCDCAA,stroke:none,color:#000
    style P7 fill:#F44747,stroke:none,color:#fff
```

## Frontend Protocol

The API returns a standard OpenAI response with optional extension fields:

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "model": "qwen2.5:3b",
  "choices": [{
    "message": {"role": "assistant", "content": "Das ist richtig! ..."},
    "finish_reason": "stop"
  }],

  "corrections": [{
    "original": "ich bin müde",
    "corrected": "ich habe mühe",
    "rule": "Use 'haben' with 'Mühe'",
    "concept_id": "haben_vs_sein",
    "severity": "warning"
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
| **Discord** | Threaded replies with embed cards |
| **Standard OpenAI client** | Just sees the text response — learning logic runs silently |

## Proactive Scheduler (Heartbeat)

```mermaid
flowchart LR
    TICK[Heartbeat tick<br/>every 60s] --> LOOP

    subgraph LOOP["For each active agent"]
        CHECK{"Time since<br/>last heartbeat<br/>≥ interval?"}
        CHECK -- No --> SKIP[Skip]
        CHECK -- Yes --> L1

        subgraph L1["For each learner"]
            R{"FSRS reviews<br/>due?"}
            R -- Yes --> MSG1["📝 Review reminder<br/>'You have N reviews due'"]

            I{"Inactive<br/>> 24h?"}
            I -- Yes --> MSG2["👋 Inactivity checkin<br/>'Want to practice?'"}

            W{"Weakest concept<br/>< 30%?"}
            W -- Yes --> MSG3["🎯 Weak spot focus<br/>'Let's work on X'"]
        end

        MSG1 --> Q[Outbound message queue]
        MSG2 --> Q
        MSG3 --> Q
    end

    Q --> ADAPTER["Channel Adapters<br/>poll /v1/outbound"]
    ADAPTER --> DELIVER["Deliver via IRC<br/>Telegram · Discord · Web push"]

    style TICK fill:#FF9800,stroke:none,color:#000
    style Q fill:#569CD6,stroke:none,color:#000
    style DELIVER fill:#4EC9B0,stroke:none,color:#000
```

## Container Stack

```mermaid
graph LR
    subgraph Docker Compose
        DB[("db<br/>pgvector/pgvector:pg16<br/>:5432")]
        API2["api<br/>FastAPI + uvicorn<br/>:8000"]
        WRK["worker<br/>Heartbeat loop"]
        CHN["channels<br/>IRC · TG · Discord"]
        WEB["web<br/>Next.js 15<br/>:3000"]
        OLL["ollama<br/>LLM inference<br/>:11434"]
    end

    API2 --> DB
    WRK --> DB
    CHN --> API2
    CHN --> DB
    WEB --> API2
    API2 --> OLL

    style DB fill:#336791,stroke:none,color:#fff
    style API2 fill:#009688,stroke:none,color:#fff
    style WRK fill:#FF9800,stroke:none,color:#fff
    style CHN fill:#9C27B0,stroke:none,color:#fff
    style WEB fill:#61DAFB,stroke:none,color:#000
    style OLL fill:#4A154B,stroke:none,color:#fff
```

## File Structure

```
learnharness/
├── app/
│   ├── main.py                  # FastAPI app, lifespan, router registration
│   ├── config.py                # Environment-driven settings
│   ├── db.py                    # Async SQLAlchemy session
│   ├── models.py                # All ORM models (9 tables)
│   ├── schemas.py               # Pydantic request/response models
│   ├── harness.py               # Main agent chat processing pipeline
│   ├── tools.py                 # Agent tools (web_search, wikipedia, arxiv)
│   ├── worker.py                # Background heartbeat worker
│   ├── routers/
│   │   ├── chat.py              # POST /v1/chat/completions
│   │   ├── agents.py            # Agent + Learner CRUD
│   │   ├── mastery.py           # Knowledge state + graph queries
│   │   ├── reviews.py           # FSRS review management
│   │   └── heartbeat.py         # Outbound message queue
│   ├── channels/
│   │   ├── base.py              # BaseChannelAdapter + AccessControl
│   │   ├── irc.py               # IRC adapter (asyncio sockets)
│   │   ├── telegram.py          # Telegram adapter (httpx long-poll)
│   │   ├── discord.py           # Discord adapter (websockets + REST)
│   │   └── manager.py           # Channel lifecycle manager
│   └── engine/
│       ├── llm.py               # OpenAI-compatible LLM router + instructor
│       ├── fsrs_sched.py        # FSRS spaced repetition
│       ├── knowledge_tracing.py # BKT mastery estimation
│       └── knowledge_graph.py   # LLM concept extraction + graph mgmt
├── web/                         # Next.js 15 frontend
│   └── src/app/
│       ├── page.tsx             # Agent management (home)
│       ├── chat/page.tsx        # Chat interface
│       ├── mastery/page.tsx     # FSRS + BKT dashboard
│       └── settings/page.tsx    # Settings
├── tests/
│   ├── test_fsrs_time.py        # Time-simulated FSRS tests (20)
│   ├── test_bkt_comprehensive.py # BKT convergence/dynamics (19)
│   ├── test_channels.py         # Channel access control (20)
│   ├── test_schemas.py          # Pydantic validation (19)
│   ├── test_models.py           # Model validation (16)
│   ├── test_bkt.py              # KnowledgeTracer (9)
│   ├── test_schemas_extended.py # Extended schemas (7)
│   ├── test_config.py           # Settings (6)
│   ├── test_knowledge_tracing.py # Basic BKT (5)
│   ├── test_tools_registry.py   # Tool registry (4)
│   ├── test_fsrs.py             # Basic FSRS (4)
│   └── test_learning_simulation.py # E2E conversation
├── .github/workflows/
│   ├── tests.yml                # Lint + test (Python 3.11+3.12) + web build
│   ├── docker.yml               # Docker compose verification
│   └── docker-publish.yml       # Build & publish to GHCR
├── docs/
│   ├── ARCHITECTURE.md          # This file
│   └── VISION.md                # Vision + design decisions
├── deploy/                      # Demo deployment configs
├── compose.yaml                 # Full stack: db + api + worker + channels + web + ollama
├── Dockerfile                   # Multi-stage: api, worker, channels targets
├── pyproject.toml
└── README.md
```
