#!/usr/bin/env python3
"""Initialize database: create pgvector extension + all tables.

Used as the startup command before running the API or worker.
"""

import asyncio

from sqlalchemy import text

from app.db import Base, engine
# Import all models so they register with Base.metadata
from app.models import (  # noqa: F401
    Agent, Learner, Concept, ConceptEdge, Mastery, ReviewItem,
    Interaction, ErrorPattern, OutboundMessage,
)


async def init():
    async with engine.begin() as conn:
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception:
            pass  # Already exists — ignore
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("Database initialized: pgvector extension + all tables created")


if __name__ == "__main__":
    asyncio.run(init())
