"""LearnHarness — domain-agnostic adaptive learning harness.

OpenAI-compatible chat API with transparent learning intelligence:
- FSRS spaced repetition
- Bayesian knowledge tracing
- LLM-auto-constructed knowledge graphs
- Agent persona system (master prompt defines behavior)
- Tools (web_search, browser, arxiv, wikipedia)
- Background heartbeat worker
"""

import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import Base
from app.db import engine
from app.models import register_all_models

register_all_models()
from app.routers import agents  # noqa: E402
from app.routers import chat  # noqa: E402
from app.routers import heartbeat  # noqa: E402
from app.routers import mastery  # noqa: E402
from app.routers import reviews  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Migrations handled by alembic (compose.yaml runs `alembic upgrade head`)
    # For dev without alembic, create_all still works as fallback
    async with engine.begin() as conn:
        from sqlalchemy import text

        result = await conn.execute(
            text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
        )
        count = result.scalar()
        if count == 0:
            # Fresh DB — no tables means alembic didn't run
            with contextlib.suppress(Exception):
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
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

app.include_router(chat.router, tags=["chat"])
app.include_router(agents.router, tags=["agents"])
app.include_router(mastery.router, tags=["mastery"])
app.include_router(reviews.router, tags=["reviews"])
app.include_router(heartbeat.router, tags=["outbound"])


@app.get("/")
async def root():
    return {
        "name": "LearnHarness",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": {
            "chat": "POST /v1/chat/completions",
            "agents": "GET/POST /v1/agents",
            "mastery": "GET /v1/mastery/{learner_id}",
            "reviews": "GET /v1/reviews/{learner_id}",
            "outbound": "GET /v1/outbound",
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
