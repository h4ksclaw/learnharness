"""Agent CRUD router — create and manage tutor personas."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.persona import create_agent, PRESETS
from app.db import get_db
from app.models import Agent, Learner
from app.schemas import AgentCreate, AgentOut, LearnerCreate, LearnerOut

router = APIRouter()


@router.get("/v1/agents", response_model=list[AgentOut])
async def list_agents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).order_by(Agent.created_at))
    return result.scalars().all()


@router.post("/v1/agents", response_model=AgentOut, status_code=201)
async def create_agent_endpoint(req: AgentCreate, db: AsyncSession = Depends(get_db)):
    agent = create_agent(
        name=req.name,
        domain=req.domain,
        template=req.rules.get("template", "language_tutor"),
        response_language=req.response_language,
        target_language=req.target_language,
        level=req.level,
        extra_rules=req.rules.get("extra_rules", ""),
        rules=req.rules,
        proactive=req.proactive,
        llm_model=req.llm_model,
        description=req.description,
        system_prompt=req.system_prompt,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("/v1/agents/presets", response_model=dict)
async def list_presets():
    """List available agent presets for quick creation."""
    return {name: f"Preset for {name}" for name in PRESETS}


@router.post("/v1/agents/presets/{preset_name}", response_model=AgentOut, status_code=201)
async def create_from_preset(preset_name: str, db: AsyncSession = Depends(get_db)):
    """Create an agent from a preset (german_tutor, spanish_buddy, python_mentor, japanese_tutor)."""
    if preset_name not in PRESETS:
        raise HTTPException(404, f"Preset '{preset_name}' not found. Available: {list(PRESETS.keys())}")
    agent = PRESETS[preset_name]()
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


@router.delete("/v1/agents/{agent_id}", status_code=204)
async def delete_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    agent = (await db.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    await db.delete(agent)
    await db.commit()


# ─── Learner endpoints ───

@router.post("/v1/learners", response_model=LearnerOut, status_code=201)
async def create_learner(req: LearnerCreate, db: AsyncSession = Depends(get_db)):
    import uuid
    learner = Learner(id=str(uuid.uuid4()), agent_id=req.agent_id, name=req.name, preferences=req.preferences)
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
