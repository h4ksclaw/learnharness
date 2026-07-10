"""Mastery and knowledge graph router."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Mastery, Concept, ConceptEdge, ErrorPattern
from app.schemas import MasteryOut, MasteryGraphOut

router = APIRouter()


@router.get("/v1/mastery/{learner_id}", response_model=list[MasteryOut])
async def get_mastery(learner_id: str, db: AsyncSession = Depends(get_db)):
    """Get the learner's current mastery state across all concepts."""
    stmt = (
        select(Mastery, Concept)
        .join(Concept, Mastery.concept_id == Concept.id)
        .where(Mastery.learner_id == learner_id)
        .order_by(Mastery.p_mastery)
    )
    rows = (await db.execute(stmt)).all()
    return [
        MasteryOut(
            concept_id=m.concept_id,
            concept_name=c.name,
            category=c.category,
            p_mastery=m.p_mastery,
            interactions_count=m.interactions_count,
            correct_count=m.correct_count,
            last_updated=m.last_updated,
        )
        for m, c in rows
    ]


@router.get("/v1/mastery/{learner_id}/graph", response_model=MasteryGraphOut)
async def get_mastery_graph(learner_id: str, db: AsyncSession = Depends(get_db)):
    """Get the knowledge graph with mastery overlay — for visualization."""
    # Get all mastery records for this learner
    mastery_stmt = select(Mastery).where(Mastery.learner_id == learner_id)
    mastery_map = {m.concept_id: m for m in (await db.execute(mastery_stmt)).scalars().all()}

    # Get the learner's agent to scope concepts
    from app.models import Learner
    learner = (await db.execute(select(Learner).where(Learner.id == learner_id))).scalar_one_or_none()
    if not learner:
        raise HTTPException(404, "Learner not found")

    # Get all concepts for this agent
    concepts = (
        await db.execute(select(Concept).where(Concept.agent_id == learner.agent_id))
    ).scalars().all()

    # Build nodes with mastery overlay
    nodes = []
    for c in concepts:
        m = mastery_map.get(c.id)
        nodes.append({
            "id": c.id,
            "name": c.name,
            "category": c.category,
            "difficulty": c.difficulty,
            "mastery": m.p_mastery if m else None,
            "interactions": m.interactions_count if m else 0,
        })

    # Get edges
    concept_ids = {c.id for c in concepts}
    edges_stmt = select(ConceptEdge).where(
        ConceptEdge.source_id.in_(concept_ids),
        ConceptEdge.target_id.in_(concept_ids),
    )
    edges_result = (await db.execute(edges_stmt)).scalars().all()
    edges = [
        {
            "source": e.source_id,
            "target": e.target_id,
            "type": e.edge_type,
        }
        for e in edges_result
    ]

    return MasteryGraphOut(nodes=nodes, edges=edges)


@router.get("/v1/mastery/{learner_id}/errors", response_model=list[dict])
async def get_error_patterns(learner_id: str, db: AsyncSession = Depends(get_db)):
    """Get recurring error patterns for this learner."""
    stmt = (
        select(ErrorPattern, Concept)
        .join(Concept, ErrorPattern.concept_id == Concept.id)
        .where(ErrorPattern.learner_id == learner_id)
        .order_by(ErrorPattern.count.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "concept_name": c.name,
            "error_type": ep.error_type,
            "count": ep.count,
            "examples": ep.examples[:5],
            "last_seen": ep.last_seen.isoformat(),
        }
        for ep, c in rows
    ]
