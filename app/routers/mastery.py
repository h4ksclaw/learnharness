"""Mastery and knowledge graph router."""

from typing import Annotated
from typing import Any

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Concept
from app.models import ConceptEdge
from app.models import ErrorPattern
from app.models import Learner
from app.models import Mastery
from app.schemas import CategoryProgress
from app.schemas import ConceptCreate
from app.schemas import ConceptOut
from app.schemas import MasteryOut

router = APIRouter()


@router.get("/v1/mastery/{learner_id}", response_model=list[MasteryOut])
async def get_mastery(
    learner_id: str, db: Annotated[AsyncSession, Depends(get_db)]
) -> list[MasteryOut]:
    """Get the learner's mastery state across all concepts."""
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


@router.get("/v1/mastery/{learner_id}/categories", response_model=list[CategoryProgress])
async def get_category_progress(
    learner_id: str, db: Annotated[AsyncSession, Depends(get_db)]
) -> list[CategoryProgress]:
    """Get progress grouped by category."""
    stmt = (
        select(Mastery, Concept)
        .join(Concept, Mastery.concept_id == Concept.id)
        .where(Mastery.learner_id == learner_id)
    )
    rows = (await db.execute(stmt)).all()

    categories: dict[str, list] = {}
    for mastery, concept in rows:
        cat = concept.category
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(
            {
                "concept_id": concept.id,
                "name": concept.name,
                "mastery": mastery.p_mastery,
                "difficulty": concept.difficulty,
            }
        )

    result = []
    for cat, concepts in categories.items():
        avg = sum(c["mastery"] for c in concepts) / len(concepts)
        result.append(
            CategoryProgress(
                category=cat,
                concept_count=len(concepts),
                avg_mastery=avg,
                concepts=concepts,
            )
        )
    return result


@router.get("/v1/mastery/{learner_id}/graph")
async def get_mastery_graph(
    learner_id: str, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict[str, Any]:
    """Get the knowledge graph with mastery overlay."""
    learner = (
        await db.execute(select(Learner).where(Learner.id == learner_id))
    ).scalar_one_or_none()
    if not learner:
        raise HTTPException(404, "Learner not found")

    mastery_map = {}
    mastery_stmt = select(Mastery).where(Mastery.learner_id == learner_id)
    for m in (await db.execute(mastery_stmt)).scalars().all():
        mastery_map[m.concept_id] = m

    concepts = (
        (await db.execute(select(Concept).where(Concept.agent_id == learner.agent_id)))
        .scalars()
        .all()
    )

    nodes = []
    for c in concepts:
        mastery_entry: Mastery | None = mastery_map.get(c.id)
        nodes.append(
            {
                "id": c.id,
                "name": c.name,
                "category": c.category,
                "difficulty": c.difficulty,
                "mastery": mastery_entry.p_mastery if mastery_entry else None,
                "interactions": mastery_entry.interactions_count if mastery_entry else 0,
            }
        )

    concept_ids = {c.id for c in concepts}
    edges_stmt = select(ConceptEdge).where(
        ConceptEdge.source_id.in_(concept_ids),
        ConceptEdge.target_id.in_(concept_ids),
    )
    edges = [
        {"source": e.source_id, "target": e.target_id, "type": e.edge_type}
        for e in (await db.execute(edges_stmt)).scalars().all()
    ]
    return {"nodes": nodes, "edges": edges}


@router.get("/v1/mastery/{learner_id}/errors", response_model=list[dict])
async def get_error_patterns(
    learner_id: str, db: Annotated[AsyncSession, Depends(get_db)]
) -> list[dict[str, Any]]:
    """Get recurring error patterns."""
    stmt = (
        select(ErrorPattern, Concept)
        .join(Concept, ErrorPattern.concept_id == Concept.id)
        .where(ErrorPattern.learner_id == learner_id)
        .order_by(ErrorPattern.count.desc())
    )
    return [
        {
            "concept_name": c.name,
            "error_type": ep.error_type,
            "count": ep.count,
            "examples": ep.examples[:5],
            "last_seen": ep.last_seen.isoformat(),
        }
        for ep, c in (await db.execute(stmt)).all()
    ]


# ─── Concept management ───


@router.post("/v1/concepts", response_model=ConceptOut, status_code=201)
async def add_concept(
    req: ConceptCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConceptOut:
    """Manually add a concept to an agent's knowledge graph."""
    import uuid

    from app.models import Concept

    concept = Concept(
        id=str(uuid.uuid4()),
        agent_id=req.agent_id,
        name=req.name,
        category=req.category,
        description=req.description,
        difficulty=req.difficulty,
    )
    db.add(concept)
    await db.commit()
    await db.refresh(concept)
    return ConceptOut.model_validate(concept)
