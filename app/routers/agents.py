"""Agent CRUD — create and manage tutor agents."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Agent, Learner
from app.schemas import AgentCreate, AgentOut, LearnerCreate, LearnerOut

router = APIRouter()


@router.get("/v1/agents", response_model=list[AgentOut])
async def list_agents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).order_by(Agent.created_at))
    return result.scalars().all()


@router.post("/v1/agents", response_model=AgentOut, status_code=201)
async def create_agent(req: AgentCreate, db: AsyncSession = Depends(get_db)):
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
    return agent


@router.get("/v1/agents/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    agent = (await db.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent


@router.put("/v1/agents/{agent_id}", response_model=AgentOut)
async def update_agent(agent_id: str, req: AgentCreate, db: AsyncSession = Depends(get_db)):
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
    return agent


@router.delete("/v1/agents/{agent_id}", status_code=204)
async def delete_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    agent = (await db.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    await db.delete(agent)
    await db.commit()


# ─── Learners ───

@router.post("/v1/learners", response_model=LearnerOut, status_code=201)
async def create_learner(req: LearnerCreate, db: AsyncSession = Depends(get_db)):
    learner = Learner(
        id=str(uuid.uuid4()), agent_id=req.agent_id, name=req.name, preferences=req.preferences
    )
    db.add(learner)
    await db.commit()
    await db.refresh(learner)
    return learner


@router.get("/v1/learners/{learner_id}", response_model=LearnerOut)
async def get_learner(learner_id: str, db: AsyncSession = Depends(get_db)):
    learner = (await db.execute(select(Learner).where(Learner.id == learner_id))).scalar_one_or_none()
    if not learner:
        raise HTTPException(404, "Learner not found")
    return learner
