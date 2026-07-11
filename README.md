# LearnHarness

![Tests](https://github.com/h4ksclaw/learnharness/actions/workflows/tests.yml/badge.svg)
![Docker](https://github.com/h4ksclaw/learnharness/actions/workflows/docker.yml/badge.svg)
![GHCR](https://github.com/h4ksclaw/learnharness/actions/workflows/docker-publish.yml/badge.svg)

**Open-source, self-hosted adaptive learning platform.** Create AI tutor agents with spaced repetition, knowledge tracing, and multi-channel delivery — for any subject.

- **Any LLM** — works with local Ollama, z.ai, OpenAI, Groq, vLLM, or any OpenAI-compatible API
- **Any channel** — web UI, IRC, Telegram, Discord
- **Smart learning** — FSRS spaced repetition + Bayesian knowledge tracing + LLM-built knowledge graphs
- **Self-hosted** — your data, your models, your rules

## Quick Start

```bash
git clone https://github.com/h4ksclaw/learnharness.git
cd learnharness
cp .env.example .env    # adjust LLM backend if needed
docker compose up -d
```

| Service | URL | |
|---------|-----|-|
| API | http://localhost:8000 | OpenAPI docs at `/docs` |
| Web UI | http://localhost:3000 | Agent management, chat, mastery dashboard |

## Configuration

All config is via environment variables. Copy `.env.example` and edit:

```bash
cp .env.example .env
```

### LLM Backend

Works with **any OpenAI-compatible endpoint**. Set three variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_BASE_URL` | `http://ollama:11434/v1` | API endpoint URL |
| `LLM_MODEL` | `qwen2.5:3b` | Model name |
| `LLM_API_KEY` | `not-needed` | API key (omit for local, set for cloud) |

**Common setups:**

```bash
# Local Ollama (default — no API key, runs in Docker)
LLM_BASE_URL=http://ollama:11434/v1
LLM_MODEL=qwen2.5:3b

# z.ai
LLM_BASE_URL=https://api.z.ai/api/paas/v4
LLM_MODEL=glm-4.6
LLM_API_KEY=your-key

# OpenAI
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
LLM_API_KEY=sk-...

# Groq (free tier)
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
LLM_API_KEY=your-key
```

When using a cloud LLM (no local Ollama needed), disable the Ollama container:

```bash
docker compose up -d db api worker web channels
```

## Usage

### Create an Agent

```bash
curl -X POST localhost:8000/v1/agents -H 'Content-Type: application/json' -d '{
  "name": "German Buddy",
  "master_prompt": "You are a friendly German tutor. Only respond in German. Correct mistakes gently.",
  "tools": ["web_search", "wikipedia"],
  "heartbeat_interval": 300
}'
```

### Chat

```bash
curl -X POST localhost:8000/v1/chat/completions -H 'Content-Type: application/json' -d '{
  "agent_id": "<id from above>",
  "messages": [{"role": "user", "content": "Ich bin müde heute"}]
}'
```

Or use the **Web UI** at http://localhost:3000 for a full chat experience with corrections, mastery tracking, and review scheduling.

### API Endpoints

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
| `/v1/reviews/{id}/answer` | POST | Submit review answer |
| `/v1/outbound` | GET | Outbound messages (channels poll) |

Full OpenAPI spec at `http://localhost:8000/docs`.

## Prebuilt Images

```bash
docker pull ghcr.io/h4ksclaw/learnharness/api:latest
docker pull ghcr.io/h4ksclaw/learnharness/worker:latest
docker pull ghcr.io/h4ksclaw/learnharness/channels:latest
```

## Documentation

- [Architecture & Design](docs/ARCHITECTURE.md) — system diagrams, data model, chat pipeline, scheduler
- [Contributing](CONTRIBUTING.md) — development setup, testing, code style, adding tools/channels
- [Vision](docs/VISION.md) — design decisions and roadmap

## Code Quality

![Scorecard](scorecard.png)

## License

MIT
