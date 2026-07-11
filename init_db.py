#!/usr/bin/env python3
"""Initialize database: create pgvector extension + all tables.

Used as the startup command before running the API or worker.
"""

import asyncio
import logging

from sqlalchemy import text

from app.db import Base
from app.db import engine

# Import all models so they register with Base.metadata
from app.models import Agent  # noqa: F401
from app.models import Concept  # noqa: F401
from app.models import ConceptEdge  # noqa: F401
from app.models import ErrorPattern  # noqa: F401
from app.models import Interaction  # noqa: F401
from app.models import Learner  # noqa: F401
from app.models import Mastery  # noqa: F401
from app.models import OutboundMessage  # noqa: F401
from app.models import ReviewItem  # noqa: F401

log = logging.getLogger(__name__)


async def init():
    async with engine.begin() as conn:
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception:
            log.warning("Could not create pgvector extension (may already exist)")
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("Database initialized: pgvector extension + all tables created")


if __name__ == "__main__":
    asyncio.run(init())
