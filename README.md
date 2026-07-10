# LearnHarness

**An open-source, self-hosted adaptive learning platform with AI-powered conversation, spaced repetition, and knowledge tracing.**

Domain-agnostic by design — works for languages, programming, science, anything. The backend is a standalone API; any frontend (web, IRC bot, Telegram, mobile app) connects to it.

---

## Quick Start

```bash
git clone https://github.com/mattf/learnharness.git
cd learnharness
docker compose up -d
```

API at `http://localhost:8000`. Web UI at `http://localhost:3000`.

---

## What Is This?

LearnHarness is a **learning harness** — a system that wraps an LLM in pedagogical intelligence. Instead of a chatbot that gives answers, it's a tutor that:

- **Tracks what you know** — builds a knowledge graph of concepts and your mastery level for each one, updated from every message you send
- **Corrects you inline** — detects errors in your messages and suggests corrections as expandable notes, not lecture dumps
- **Remembers and reviews** — uses FSRS spaced repetition to schedule when to bring up old material so you don't forget
- **Adapts to you** — difficulty, pacing, and topics adjust based on Bayesian Knowledge Tracing of your competency
- **Reaches out** — proactive heartbeat system pings you when reviews are due or you've been inactive
- **Is any tutor you want** — create custom agent personas: "German tutor that only speaks German", "Python mentor that uses Socratic method", etc.

### Why?

The pieces of adaptive learning exist — Duolingo has spaced repetition + adaptive difficulty, Khanmigo has Socratic AI tutoring, Anki has FSRS. **Nobody has combined them into a single open system that works for any subject.** The technology is all published, has open-source implementations, and the timing is right.

See `docs/VISION.md` for the full reasoning.

---

## Architecture

```
                    ┌──────────────────────────────────┐
                    │         Any Frontend              │
                    │  Web UI · IRC bot · Telegram ·    │
                    │  Flutter app · CLI · Anything     │
                    └────────────┬─────────────────────┘
                                 │ HTTP / SSE
                    ┌────────────▼─────────────────────┐
                    │     FastAPI Backend (API)         │
                    │                                   │
                    │  POST /v1/chat/completions        │
                    │  (OpenAI-compatible)              │
                    │                                   │
                    │  ┌─────────────────────────────┐  │
                    │  │     Agent Harness            │  │
                    │  │  persona + context builder   │  │
                    │  └──────┬──────────────────────┘  │
                    │         │                         │
                    │  ┌──────▼──────────────────────┐  │
                    │  │   Knowledge Graph Engine     │  │
                    │  │  concept extraction (LLM)    │  │
                    │  │  mastery tracking (BKT)      │  │
                    │  │  spaced repetition (FSRS)    │  │
                    │  │  semantic search (pgvector)  │  │
                    │  └──────┬──────────────────────┘  │
                    │         │                         │
                    │  ┌──────▼──────────────────────┐  │
                    │  │     LLM Router               │  │
                    │  │  Ollama · OpenAI · vLLM ·    │  │
                    │  │  DeepSeek · Any OAI-compat   │  │
                    │  └─────────────────────────────┘  │
                    └────────────┬─────────────────────┘
                                 │
                    ┌────────────▼─────────────────────┐
                    │   PostgreSQL + pgvector           │
                    │  concepts · mastery · reviews ·   │
                    │  interactions · error_patterns    │
                    └───────────────────────────────────┘
```

**Key principle**: The backend is the product. Frontends are thin clients over the API. The learning intelligence is transparent — it runs silently behind an OpenAI-compatible chat endpoint so any existing chat client works out of the box.

See `docs/ARCHITECTURE.md` for details.

---

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Backend | **FastAPI** (Python 3.11+) | Async, type-safe, auto-docs, ecosystem |
| Database | **PostgreSQL + pgvector** | Relational + vector search in one DB, no extra services |
| Spaced Repetition | **py-fsrs** (FSRS algorithm) | State-of-the-art, 30-50% fewer reviews than SM-2 |
| Knowledge Tracing | **BKT** (custom impl) | Bayesian mastery estimation, proven since 1995 |
| LLM | **Any OpenAI-compatible** | Ollama (local/free), OpenAI, DeepSeek, vLLM, LM Studio |
| Frontend (default) | **Next.js** (planned) | Rich UI with dynamic components for corrections, graphs |

---

## Configuration

All config via environment variables or `.env` file:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://lh:lh_dev@localhost:5433/learnharness

# LLM (defaults to local Ollama — free, no API key)
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.2:3b
LLM_API_KEY=not-needed

# Or use any cloud provider:
# LLM_BASE_URL=https://api.openai.com/v1
# LLM_MODEL=gpt-4o
# LLM_API_KEY=sk-...
```

---

## Project Status

**Phase 1: Backend Foundation** ✅
- [x] FastAPI app with OpenAI-compatible chat endpoint
- [x] FSRS spaced repetition scheduling
- [x] Bayesian Knowledge Tracing
- [x] LLM-powered knowledge graph engine
- [x] Agent persona system with presets
- [x] Proactive scheduler (heartbeat)
- [x] 14/14 tests passing

**Phase 2: Core Features** 🔧
- [ ] Embedding generation for semantic concept search
- [ ] `instructor`-based extraction (robust structured LLM output)
- [ ] Recursive CTE graph traversal for prerequisite-aware queries
- [ ] Alembic migrations
- [ ] End-to-end integration tests with Docker

**Phase 3: Frontend** 📋
- [ ] Web UI (management dashboard + chat with corrections)
- [ ] IRC bot frontend
- [ ] Telegram bot frontend

**Phase 4: Polish** 📋
- [ ] Knowledge graph visualization
- [ ] Analytics dashboard
- [ ] Import/export learner data
- [ ] Multi-agent support (one learner, multiple tutors)

---

## License

MIT — do whatever you want.
