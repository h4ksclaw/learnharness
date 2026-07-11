# LearnHarness

![Tests](https://github.com/h4ksclaw/learnharness/actions/workflows/tests.yml/badge.svg)
![Docker](https://github.com/h4ksclaw/learnharness/actions/workflows/docker.yml/badge.svg)
![GHCR](https://github.com/h4ksclaw/learnharness/actions/workflows/docker-publish.yml/badge.svg)

**Open-source, self-hosted adaptive learning platform.** Create AI tutor agents with master prompts, tools, and channels. The agent teaches, tracks knowledge, and reviews — for any subject.

**Prebuilt images:**
- `docker pull ghcr.io/h4ksclaw/learnharness/api:latest`
- `docker pull ghcr.io/h4ksclaw/learnharness/worker:latest`
- `docker pull ghcr.io/h4ksclaw/learnharness/channels:latest`

## Quick Start

```bash
git clone https://github.com/h4ksclaw/learnharness.git
cd learnharness
docker compose up -d
```

- **API**: `http://localhost:8000` · **Docs**: `http://localhost:8000/docs`
- **Web UI**: `http://localhost:3000` (agent management, chat, mastery dashboard)
- Includes Postgres+pgvector, API server, background worker, channel adapters, and Ollama.

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
    U[User sends message] --> A["① LLM Analyzes<br/>Extracts concepts, corrections, mastery signals"]
    A --> B["② Knowledge Graph Updated<br/>Concepts + prerequisite edges"]
    B --> C["③ BKT Mastery Updated<br/>Per-concept probability shifts"]
    C --> D["④ Learner Context Injected<br/>Weak areas + strong areas → system prompt"]
    D --> E["⑤ LLM Generates Response<br/>Can call tools: web_search, arxiv, wikipedia"]
    E --> F["⑥ Returns Enriched Response<br/>OpenAI-shaped + corrections + mastery deltas + due reviews"]

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
        Web["Web UI<br/>(Next.js 15)"]
        IRC[IRC Bot]
        TG[Telegram Bot]
        DC[Discord Bot]
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
        CHAN["Channel Manager<br/>IRC · Telegram · Discord<br/>Access control + routing"]
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
    CHAN --> API
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
        CHN["channels<br/>IRC · TG · Discord<br/>adapters"]
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

## Tech Stack

| Layer | Choice |
|-------|--------|
| Backend | FastAPI (Python 3.11+) |
| Frontend | Next.js 15 (React, TypeScript) |
| Database | PostgreSQL + pgvector |
| Spaced Repetition | FSRS (py-fsrs) |
| Knowledge Tracing | BKT (custom) |
| Migrations | Alembic |
| LLM | Any OpenAI-compatible (Ollama default, Groq for demo) |
| Tools | web_search, browse_url, wikipedia, arxiv |
| Channels | IRC, Telegram, Discord adapters with access control |

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/v1/chat/completions` | POST | Chat with agent (OpenAI-compatible) |
| `/v1/agents` | GET/POST | List/create agents |
| `/v1/agents/{id}` | GET/PUT/DELETE | Manage agent |
| `/v1/learners` | POST | Create learner |
| `/v1/mastery/{id}` | GET | Knowledge state |
| `/v1/mastery/{id}/categories` | GET | Progress by category |
| `/v1/mastery/{id}/graph` | GET | Knowledge graph (nodes + edges) |
| `/v1/mastery/{id}/errors` | GET | Error patterns by concept |
| `/v1/concepts` | POST | Add concept to knowledge graph |
| `/v1/reviews/{id}` | GET | Due FSRS reviews |
| `/v1/reviews/{id}/all` | GET | All review items |
| `/v1/reviews/{id}/answer` | POST | Submit review answer (rating 1-4) |
| `/v1/outbound` | GET | Outbound messages (channel adapters poll) |
| `/v1/outbound/{id}/sent` | POST | Mark outbound message as sent |
| `/` | GET | Health check |
| `/health` | GET | Service health |

## Testing

```bash
# Unit tests (no DB needed)
DATABASE_URL=sqlite+aiosqlite:///test.db pytest tests/ -v \
  --ignore=tests/test_tools.py \
  --ignore=tests/test_tools_system.py \
  --ignore=tests/test_learning_simulation.py

# With coverage
pytest tests/ --cov=app --cov-report=term-missing

# E2E integration test (requires running API + Ollama)
python tests/test_learning_simulation.py
```

### Test Coverage

| Test File | Tests | What It Covers |
|---|---|---|
| `test_fsrs_time.py` | 20 | Time-simulated FSRS: stability growth, lapse recovery, week-of-learning, rating effects |
| `test_bkt_comprehensive.py` | 19 | BKT convergence, dynamics, soft inference, recovery, boundary conditions |
| `test_schemas.py` | 19 | Pydantic validation: agent, chat, corrections, mastery, reviews |
| `test_channels.py` | 20 | Channel access control, allowlist/blocklist, DM permissions, require_mention |
| `test_models.py` | 16 | ORM models: creation, relationships, constraints |
| `test_schemas_extended.py` | 7 | ConceptCreate, OutboundMessageOut extra field, AgentOut token masking |
| `test_config.py` | 6 | Settings, defaults, DB engine |
| `test_knowledge_tracing.py` | 5 | BKT correctness: update, ceiling, floor, inference |
| `test_bkt.py` | 9 | KnowledgeTracer: mastery updates, convergence, custom parameters |
| `test_tools_registry.py` | 4 | Tool definitions, OpenAI schema generation, execution |
| `test_fsrs.py` | 4 | Basic FSRS mechanics |
| `test_tools_system.py` | 11 | Tool registry, OpenAI schemas, execution (network required) |
| `test_tools.py` | 3 | Live tool tests (network required) |
| `test_learning_simulation.py` | 6 | **E2E**: 8-turn conversation with live LLM |

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Lint and format
ruff check app/ tests/
ruff format app/ tests/

# Type check
mypy app/ --ignore-missing-imports

# Pre-commit hooks
pre-commit install
pre-commit run --all-files

# Generate a new migration after model changes
alembic revision --autogenerate -m "description of change"
```

### Code Quality Tools

| Tool | Purpose |
|------|---------|
| **ruff** | Linting (E, F, I, N, W, UP, B, SIM, C4) + formatting. One import per line. |
| **mypy** | Type checking with `warn_return_any` |
| **pre-commit** | Auto-runs ruff, ruff-format, mypy, whitespace checks on commit |
| **pytest** | 139 unit tests + e2e simulation (all passing) |
| **GitHub Actions** | CI: lint, test (Python 3.11+3.12), mypy, docker, GHCR publish |

## Project Status

- [x] FastAPI backend with OpenAI-compatible chat
- [x] FSRS spaced repetition
- [x] BKT knowledge tracing
- [x] LLM knowledge graph engine
- [x] Tools system (web_search, browse_url, wikipedia, arxiv)
- [x] Agent model (master prompt + tools + channels + heartbeat)
- [x] Background worker with proactive scheduling
- [x] Outbound message queue for multi-channel delivery
- [x] Alembic migrations
- [x] 139 unit tests + e2e simulation (all passing)
- [x] Docker Compose (db + api + worker + channels + ollama)
- [x] GitHub Actions CI (lint + test + mypy + docker + GHCR)
- [x] ruff + mypy + pre-commit
- [x] Web UI (Next.js 15 — agent management, chat, mastery dashboard, settings)
- [x] Channel adapters (IRC, Telegram, Discord) with access control
- [x] One-command demo deployment (Groq + Docker, no GPU needed)

## Code Quality

![Scorecard](scorecard.png)

## License

MIT
