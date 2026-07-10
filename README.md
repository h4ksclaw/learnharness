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

```
User sends message
    ↓
① LLM analyzes → extracts concepts, corrections, mastery signals
② Knowledge graph updated (concepts + prerequisite edges)
③ BKT mastery updated per concept
④ Learner context injected into system prompt
⑤ LLM generates response (can use tools: web_search, arxiv, wikipedia)
⑥ Returns OpenAI-shaped response + corrections, mastery deltas, due reviews

Background worker (heartbeat):
  Checks FSRS reviews → generates proactive messages → writes to outbound queue
```

## Architecture

```
                    ┌────────────────────────────────┐
                    │        Any Frontend             │
                    │  Web UI · IRC bot · Telegram ·  │
                    │  Flutter · CLI · Anything       │
                    └──────────┬─────────────────────┘
                               │ HTTP
                    ┌──────────▼─────────────────────┐
                    │     FastAPI Backend (API)       │
                    │  POST /v1/chat/completions      │
                    │  (OpenAI-compatible)            │
                    ├──────────────────────────────────┤
                    │  Agent Harness                   │
                    │  master prompt + learner context │
                    │  + tool execution loop           │
                    ├──────┬──────┬──────┬─────────────┤
                    │ KG   │ BKT  │ FSRS │ Worker      │
                    │ Engine│      │      │ (heartbeat) │
                    ├──────┴──────┴──────┴─────────────┤
                    │  LLM Router (any OAI-compatible) │
                    └──────────┬─────────────────────┘
                    ┌──────────▼─────────────────────┐
                    │  PostgreSQL + pgvector          │
                    └────────────────────────────────┘
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
- [x] 14/14 tests passing
- [x] Docker Compose (db + api + worker + ollama)
- [ ] Alembic migrations
- [ ] Web UI
- [ ] Channel adapters (IRC, Telegram)

## License

MIT
