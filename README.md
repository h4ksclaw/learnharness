# LearnHarness

![Tests](https://github.com/h4ksclaw/learnharness/actions/workflows/tests.yml/badge.svg)
![Docker](https://github.com/h4ksclaw/learnharness/actions/workflows/docker.yml/badge.svg)

**Open-source, self-hosted adaptive learning platform.** Create AI tutor agents with master prompts, tools, and channels. The agent teaches, tracks knowledge, and reviews — for any subject.

## Quick Start

```bash
git clone https://github.com/h4ksclaw/learnharness.git
cd learnharness
docker compose up -d
```

- **API**: `http://localhost:8000` · **Docs**: `http://localhost:8000/docs`
- Includes Postgres+pgvector, API server, background worker, and Ollama.

## Create an Agent

```bash
# Create a German tutor
curl -X POST localhost:8000/v1/agents -H 'Content-Type: application/json' -d '{
  "name": "German Buddy",
  "master_prompt": "You are a friendly German tutor. Only respond in German. Correct mistakes gently.",
  "tools": ["web_search", "wikipedia"],
  "heartbeat_interval": 300
}'
```

Then chat:
```bash
curl -X POST localhost:8000/v1/chat/completions -H 'Content-Type: application/json' -d '{
  "agent_id": "<id from above>",
  "messages": [{"role": "user", "content": "Ich bin müde heute"}]
}'
```

## How It Works

```mermaid
flowchart TD
    U[User sends message] --> A[① LLM Analyzes<br/>Extracts concepts, corrections, mastery signals]
    A --> B[② Knowledge Graph Updated<br/>Concepts + prerequisite edges]
    B --> C[③ BKT Mastery Updated<br/>Per-concept probability shifts]
    C --> D[④ Learner Context Injected<br/>Weak areas + strong areas → system prompt]
    D --> E[⑤ LLM Generates Response<br/>Can call tools: web_search, arxiv, wikipedia]
    E --> F[⑥ Returns Enriched Response<br/>OpenAI-shaped + corrections + mastery deltas + due reviews]

    style A fill:#4EC9B0,stroke:none,color:#000
    style B fill:#C586C0,stroke:none,color:#000
    style C fill:#569CD6,stroke:none,color:#000
    style D fill:#CE9178,stroke:none,color:#000
    style E fill:#4EC9B0,stroke:none,color:#000
    style F fill:#6A9955,stroke:none,color:#000
```

## Architecture

```mermaid
graph TB
    subgraph Frontends["Any Frontend"]
        Web[Web UI]
        IRC[IRC Bot]
        TG[Telegram Bot]
        CLI[CLI / curl]
    end

    Frontends -- "HTTP / OpenAI-compatible API" --> API

    subgraph Backend["FastAPI Backend"]
        API["POST /v1/chat/completions<br/>OpenAI-compatible"]

        subgraph Harness["Agent Harness"]
            MP["Master Prompt<br/>+ Learner Context<br/>+ Tool Execution Loop"]
        end

        subgraph Engines["Learning Engines"]
            KG["KG Engine<br/>Concept extraction<br/>& graph building"]
            BKT["BKT<br/>Bayesian Knowledge<br/>Tracing"]
            FSRS["FSRS<br/>Spaced Repetition<br/>Scheduler"]
        end

        WORKER["Background Worker<br/>Heartbeat scheduler<br/>→ outbound queue"]
        TOOLS["Tools<br/>web_search · browse_url<br/>wikipedia · arxiv"]
        LLM["LLM Router<br/>Ollama · vLLM · OpenAI<br/>Any OpenAI-compatible"]
    end

    subgraph Data["Data Layer"]
        PG[("PostgreSQL<br/>+ pgvector")]
        OLLAMA["Ollama<br/>qwen2.5:3b"]
    end

    API --> Harness
    MP --> KG
    MP --> BKT
    MP --> FSRS
    MP --> TOOLS
    MP --> LLM
    WORKER --> FSRS
    WORKER --> BKT
    KG --> PG
    BKT --> PG
    FSRS --> PG
    LLM --> OLLAMA

    style Frontends fill:#1e1e1e,stroke:#4EC9B0,color:#4EC9B0
    style Backend fill:#1e1e1e,stroke:#569CD6,color:#569CD6
    style Data fill:#1e1e1e,stroke:#C586C0,color:#C586C0
```

## Container Stack

```mermaid
graph LR
    subgraph Docker Compose
        DB[("db<br/>pgvector/pgvector:pg16<br/>:5432")]
        API2["api<br/>FastAPI + uvicorn<br/>:8000"]
        WRK["worker<br/>Heartbeat loop"]
        OLL["ollama<br/>LLM inference<br/>:11434"]
    end

    API2 --> DB
    WRK --> DB
    API2 --> OLL

    style DB fill:#336791,stroke:none,color:#fff
    style API2 fill:#009688,stroke:none,color:#fff
    style WRK fill:#FF9800,stroke:none,color:#fff
    style OLL fill:#4A154B,stroke:none,color:#fff
```

## Tech Stack

| Layer | Choice |
|-------|--------|
| Backend | FastAPI (Python 3.11+) |
| Database | PostgreSQL + pgvector |
| Spaced Repetition | FSRS (py-fsrs) |
| Knowledge Tracing | BKT (custom) |
| LLM | Any OpenAI-compatible (Ollama default) |
| Tools | web_search, browse_url, wikipedia, arxiv |

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/v1/chat/completions` | POST | Chat with agent (OpenAI-compatible) |
| `/v1/agents` | GET/POST | List/create agents |
| `/v1/agents/{id}` | GET/PUT/DELETE | Manage agent |
| `/v1/learners` | POST | Create learner |
| `/v1/mastery/{id}` | GET | Knowledge state |
| `/v1/mastery/{id}/categories` | GET | Progress by category |
| `/v1/mastery/{id}/graph` | GET | Knowledge graph |
| `/v1/reviews/{id}` | GET | Due FSRS reviews |
| `/v1/outbound` | GET | Outbound messages (channel adapters poll) |

## Project Status

- [x] FastAPI backend with OpenAI-compatible chat
- [x] FSRS spaced repetition
- [x] BKT knowledge tracing
- [x] LLM knowledge graph engine
- [x] Tools system (web_search, browse_url, wikipedia, arxiv)
- [x] Agent model (master prompt + tools + channels + heartbeat)
- [x] Background worker with proactive scheduling
- [x] Outbound message queue for multi-channel delivery
- [x] 55 unit tests + e2e simulation (all passing)
- [x] Docker Compose (db + api + worker + ollama)
- [x] GitHub Actions CI (Python 3.11 + 3.12)
- [ ] Alembic migrations
- [ ] Web UI
- [ ] Channel adapters (IRC, Telegram)

## License

MIT
