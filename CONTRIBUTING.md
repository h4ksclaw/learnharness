# Contributing to LearnHarness

## Development Setup

```bash
# Clone and install
git clone https://github.com/h4ksclaw/learnharness.git
cd learnharness
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Start the stack (Postgres + API + Worker + Web + Ollama)
docker compose up -d
```

## Code Style

- **Python**: ruff for lint + format. One import per line. `ruff check app/ tests/ && ruff format app/ tests/`
- **TypeScript**: Next.js defaults. `cd web && npm run lint`
- **Types**: mypy for Python (`mypy app/ --ignore-missing-imports`)

## Testing

```bash
# Unit tests (SQLite, no external deps)
DATABASE_URL=sqlite+aiosqlite:///test.db pytest tests/ -v \
  --ignore=tests/test_tools.py \
  --ignore=tests/test_tools_system.py \
  --ignore=tests/test_learning_simulation.py

# With coverage
pytest tests/ --cov=app --cov-report=term-missing

# Web build check
cd web && npm run build
```

## CI

GitHub Actions runs on every push/PR to `main`:
- **Tests**: ruff lint + format check, pytest (Python 3.11 + 3.12), mypy, Next.js build
- **Docker**: compose stack verification (DB health, pgvector)
- **GHCR**: build + publish api, worker, channels images

## Adding a New Tool

1. Add the function to `app/tools.py` with type-annotated parameters
2. Register it in `TOOL_DEFINITIONS` with name, description, and JSON schema
3. Test with `pytest tests/test_tools_registry.py`

## Adding a Channel Adapter

1. Subclass `BaseChannelAdapter` in `app/channels/`
2. Implement `connect()`, `disconnect()`, `send_message()`
3. Access control is handled by the base class via `AccessControl`
4. Add the channel type to the manager

## Database Migrations

```bash
# Generate after model changes
alembic revision --autogenerate -m "description of change"

# Apply
alembic upgrade head
```

## LLM Backend Configuration

LearnHarness works with any OpenAI-compatible API. Configure via environment variables:

| Backend | `LLM_BASE_URL` | `LLM_MODEL` | API Key |
|---------|----------------|-------------|---------|
| Ollama (local) | `http://ollama:11434/v1` | `qwen2.5:3b` | `not-needed` |
| z.ai | `https://api.z.ai/api/paas/v4` | `glm-4.6` | required |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` | required |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` | required |
| vLLM | `http://localhost:8001/v1` | your model | as configured |

See `.env.example` for all options.
