"""Agent CRUD — create and manage tutor agents."""

import uuid
from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Agent
from app.models import Learner
from app.schemas import AgentCreate
from app.schemas import AgentOut
from app.schemas import LearnerCreate
from app.schemas import LearnerOut

router = APIRouter()


@router.get("/v1/agents", response_model=list[AgentOut])
async def list_agents(db: Annotated[AsyncSession, Depends(get_db)]) -> list[AgentOut]:
    result = await db.execute(select(Agent).order_by(Agent.created_at))
    return [AgentOut.from_agent(a) for a in result.scalars().all()]


@router.post("/v1/agents", response_model=AgentOut, status_code=201)
async def create_agent(req: AgentCreate, db: Annotated[AsyncSession, Depends(get_db)]) -> AgentOut:
    agent = Agent(
        id=str(uuid.uuid4()),
        name=req.name,
        master_prompt=req.master_prompt,
        tools=req.tools,
        channels=req.channels,
        heartbeat_interval=req.heartbeat_interval,
        llm_model=req.llm_model,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return AgentOut.from_agent(agent)


@router.get("/v1/agents/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: str, db: Annotated[AsyncSession, Depends(get_db)]) -> AgentOut:
    agent = (await db.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    return AgentOut.from_agent(agent)


@router.put("/v1/agents/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: str, req: AgentCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> AgentOut:
    agent = (await db.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    agent.name = req.name
    agent.master_prompt = req.master_prompt
    agent.tools = req.tools
    agent.channels = req.channels
    agent.heartbeat_interval = req.heartbeat_interval
    agent.llm_model = req.llm_model
    await db.commit()
    await db.refresh(agent)
    return AgentOut.from_agent(agent)


@router.delete("/v1/agents/{agent_id}", status_code=204)
async def delete_agent(agent_id: str, db: Annotated[AsyncSession, Depends(get_db)]) -> None:
    agent = (await db.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    await db.delete(agent)
    await db.commit()


# ─── Learners ───


@router.post("/v1/learners", response_model=LearnerOut, status_code=201)
async def create_learner(
    req: LearnerCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> LearnerOut:
    learner = Learner(
        id=str(uuid.uuid4()), agent_id=req.agent_id, name=req.name, preferences=req.preferences
    )
    db.add(learner)
    await db.commit()
    await db.refresh(learner)
    return learner


@router.get("/v1/learners/{learner_id}", response_model=LearnerOut)
async def get_learner(learner_id: str, db: Annotated[AsyncSession, Depends(get_db)]) -> LearnerOut:
    learner = (
        await db.execute(select(Learner).where(Learner.id == learner_id))
    ).scalar_one_or_none()
    if not learner:
        raise HTTPException(404, "Learner not found")
    return learner
