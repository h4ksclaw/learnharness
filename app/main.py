"""LearnHarness API — domain-agnostic adaptive learning harness.

OpenAI-compatible chat API with transparent learning intelligence:
- FSRS spaced repetition
- Bayesian knowledge tracing
- LLM-auto-constructed knowledge graphs
- Agent persona system
- Proactive scheduling
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import Base, engine
from app.routers import chat, agents, mastery, reviews, heartbeat


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (for dev; use Alembic migrations in prod)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Enable pgvector extension
        from sqlalchemy import text
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    yield

    await engine.dispose()


app = FastAPI(
    title="LearnHarness",
    description="Domain-agnostic adaptive learning harness with FSRS and knowledge tracing",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(chat.router, tags=["chat"])
app.include_router(agents.router, tags=["agents"])
app.include_router(mastery.router, tags=["mastery"])
app.include_router(reviews.router, tags=["reviews"])
app.include_router(heartbeat.router, tags=["heartbeat"])


@app.get("/")
async def root():
    return {
        "name": "LearnHarness",
        "version": "0.1.0",
        "endpoints": {
            "chat": "POST /v1/chat/completions",
            "agents": "GET/POST /v1/agents",
            "mastery": "GET /v1/mastery/{learner_id}",
            "reviews": "GET /v1/reviews/{learner_id}",
            "heartbeat": "GET /v1/heartbeat",
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
