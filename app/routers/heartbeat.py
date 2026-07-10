"""Heartbeat router — proactive agent actions.

Endpoints for the scheduler. Frontends/bots poll or subscribe to these
to know when the agent wants to reach out to the learner.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.scheduler import proactive_scheduler
from app.db import get_db

router = APIRouter()


@router.get("/v1/heartbeat")
async def heartbeat_all(db: AsyncSession = Depends(get_db)):
    """Check all proactive learners for due actions.

    Bots/cron jobs poll this endpoint. Returns actions that should be
    pushed to the learner via whatever channel they use (IRC, Telegram, push).
    """
    results = await proactive_scheduler.check_all(db)
    return {
        "actions": [
            {
                "action": r.action.value,
                "learner_id": r.learner_id,
                "agent_id": r.agent_id,
                "message": r.message,
                "data": r.data,
            }
            for r in results
        ],
        "count": len(results),
    }


@router.get("/v1/heartbeat/{learner_id}")
async def heartbeat_learner(learner_id: str, db: AsyncSession = Depends(get_db)):
    """Check a specific learner for due actions."""
    from app.models import Agent, Learner
    from sqlalchemy import select

    learner = (await db.execute(select(Learner).where(Learner.id == learner_id))).scalar_one_or_none()
    if not learner:
        from fastapi import HTTPException
        raise HTTPException(404, "Learner not found")

    agent = (await db.execute(select(Agent).where(Agent.id == learner.agent_id))).scalar_one_or_none()
    if not agent:
        from fastapi import HTTPException
        raise HTTPException(404, "Agent not found")

    result = await proactive_scheduler.check_learner(db, learner, agent)
    return {
        "action": result.action.value,
        "message": result.message,
        "data": result.data,
    }
