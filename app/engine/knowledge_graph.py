"""Knowledge Graph engine — LLM-powered concept extraction and graph construction.

The key insight: the LLM reads the conversation and outputs structured data
(concepts, relationships, errors) that we persist as graph nodes and edges.
This makes the system domain-agnostic — works for languages, coding, math, anything.
"""

import json
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.llm import llm_router
from app.models import Concept, ConceptEdge, ErrorPattern, Mastery, Learner


# ─── Structured outputs for LLM extraction ───

class ConceptExtraction(BaseModel):
    """A concept extracted from conversation."""
    name: str
    category: str = "general"
    description: str = ""
    difficulty: float = 0.5


class EdgeExtraction(BaseModel):
    """A relationship between concepts."""
    source: str  # concept name
    target: str  # concept name
    edge_type: str = "related"  # prerequisite, related, part_of, contrasts_with


class CorrectionExtraction(BaseModel):
    """A correction or error the learner made."""
    original: str
    corrected: str
    rule: str = ""
    concept_name: str | None = None
    severity: str = "warning"


class AnalysisResult(BaseModel):
    """Full analysis of a user message."""
    concepts: list[ConceptExtraction] = Field(default_factory=list)
    edges: list[EdgeExtraction] = Field(default_factory=list)
    corrections: list[CorrectionExtraction] = Field(default_factory=list)
    # Per-concept mastery inference (0-1 confidence learner knows it)
    mastery_signals: dict[str, float] = Field(default_factory=dict)
    # Concepts that should be scheduled for review
    needs_review: list[str] = Field(default_factory=list)


# ─── Prompts ───

ANALYSIS_SYSTEM_PROMPT = """You are a learning analytics engine. You analyze a learner's message and extract structured learning data.

You return JSON with this structure:
{
  "concepts": [{"name": "...", "category": "...", "description": "...", "difficulty": 0.0-1.0}],
  "edges": [{"source": "concept_name", "target": "concept_name", "edge_type": "prerequisite|related|part_of|contrasts_with"}],
  "corrections": [{"original": "...", "corrected": "...", "rule": "...", "concept_name": "...", "severity": "error|warning|suggestion"}],
  "mastery_signals": {"concept_name": 0.0-1.0},
  "needs_review": ["concept_name"]
}

Rules:
- Extract ALL concepts present in the learner's message (grammar rules, vocabulary, syntax patterns, domain facts)
- Identify prerequisite relationships (e.g. "present tense" is prerequisite for "past tense")
- Flag "contrasts_with" for commonly confused concepts (e.g. ser/estar, por/para)
- corrections: only if the learner made actual errors. Be precise about the rule violated.
- mastery_signals: estimate 0-1 how well the learner demonstrated understanding of each concept
- needs_review: concepts where mastery_signal < 0.6 or where errors were made
- difficulty: 0=trivial, 1=very advanced

Be conservative with corrections — only flag genuine errors, not style preferences.
If the domain is a programming language, concepts are syntax patterns, functions, data structures, etc.
If it's natural language, concepts are grammar, vocabulary, pronunciation, pragmatics.
"""


class KnowledgeGraphEngine:
    """Manages the dynamic knowledge graph for a learner."""

    async def analyze_message(
        self,
        user_message: str,
        master_prompt: str,
        existing_concepts: list[str] | None = None,
    ) -> AnalysisResult:
        """Analyze a user message and extract structured learning data.

        The master_prompt gives context about what domain the agent covers.
        """
        existing_str = ", ".join(existing_concepts[:50]) if existing_concepts else "none"

        context = f"""Agent context (first 500 chars): {master_prompt[:500]}

Existing concepts in graph: {existing_str}

Learner message:
\"\"\"{user_message}\"\"\"
"""
        messages = [
            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ]

        try:
            data = await llm_router.complete_json(messages, temperature=0.2)
            return AnalysisResult(**data)
        except Exception:
            # If analysis fails, return empty — the chat still works
            return AnalysisResult()

    async def upsert_concepts(
        self,
        db: AsyncSession,
        agent_id: str,
        concepts: list[ConceptExtraction],
    ) -> dict[str, Concept]:
        """Create or update concepts. Returns name→Concept mapping."""
        result = {}
        for c in concepts:
            # Check if concept exists (by name within this agent's domain)
            stmt = select(Concept).where(
                Concept.agent_id == agent_id,
                Concept.name == c.name,
            )
            existing = (await db.execute(stmt)).scalar_one_or_none()

            if existing:
                # Update description if richer
                if len(c.description) > len(existing.description or ""):
                    existing.description = c.description
                existing.difficulty = c.difficulty
                result[c.name] = existing
            else:
                concept = Concept(
                    id=str(uuid.uuid4()),
                    agent_id=agent_id,
                    name=c.name,
                    category=c.category,
                    description=c.description,
                    difficulty=c.difficulty,
                )
                db.add(concept)
                result[c.name] = concept

        await db.flush()
        return result

    async def add_edges(
        self,
        db: AsyncSession,
        concept_map: dict[str, Concept],
        edges: list[EdgeExtraction],
    ) -> int:
        """Add edges between concepts. Returns count of new edges."""
        added = 0
        for edge in edges:
            source = concept_map.get(edge.source)
            target = concept_map.get(edge.target)
            if not source or not target:
                continue

            # Check if edge already exists
            stmt = select(ConceptEdge).where(
                ConceptEdge.source_id == source.id,
                ConceptEdge.target_id == target.id,
                ConceptEdge.edge_type == edge.edge_type,
            )
            existing = (await db.execute(stmt)).scalar_one_or_none()
            if existing:
                continue

            db.add(ConceptEdge(
                source_id=source.id,
                target_id=target.id,
                edge_type=edge.edge_type,
            ))
            added += 1

        await db.flush()
        return added

    async def update_mastery(
        self,
        db: AsyncSession,
        learner_id: str,
        concept_map: dict[str, Concept],
        mastery_signals: dict[str, float],
    ) -> dict[str, dict]:
        """Update mastery records from LLM inference signals.

        Returns {concept_name: {"before": float, "after": float, "delta": float}}
        """
        from app.engine.knowledge_tracing import knowledge_tracer

        deltas = {}
        for name, confidence in mastery_signals.items():
            concept = concept_map.get(name)
            if not concept:
                continue

            # Get or create mastery record
            stmt = select(Mastery).where(
                Mastery.learner_id == learner_id,
                Mastery.concept_id == concept.id,
            )
            mastery = (await db.execute(stmt)).scalar_one_or_none()

            if not mastery:
                mastery = Mastery(
                    learner_id=learner_id,
                    concept_id=concept.id,
                    p_mastery=knowledge_tracer.prior,
                )
                db.add(mastery)

            before = mastery.p_mastery
            after, delta = knowledge_tracer.infer_from_chat(before, confidence)

            mastery.p_mastery = after
            mastery.interactions_count += 1
            mastery.last_updated = datetime.now(timezone.utc)

            deltas[name] = {"before": before, "after": after, "delta": delta, "concept_id": concept.id}

        await db.flush()
        return deltas

    async def record_errors(
        self,
        db: AsyncSession,
        learner_id: str,
        concept_map: dict[str, Concept],
        corrections: list[CorrectionExtraction],
    ) -> list[ErrorPattern]:
        """Record error patterns for recurring mistake tracking."""
        new_patterns = []
        for corr in corrections:
            if not corr.concept_name:
                continue
            concept = concept_map.get(corr.concept_name)
            if not concept:
                continue

            stmt = select(ErrorPattern).where(
                ErrorPattern.learner_id == learner_id,
                ErrorPattern.concept_id == concept.id,
                ErrorPattern.error_type == corr.rule,
            )
            pattern = (await db.execute(stmt)).scalar_one_or_none()

            if pattern:
                pattern.count += 1
                pattern.examples.append({"original": corr.original, "corrected": corr.corrected})
                pattern.last_seen = datetime.now(timezone.utc)
            else:
                pattern = ErrorPattern(
                    learner_id=learner_id,
                    concept_id=concept.id,
                    error_type=corr.rule,
                    examples=[{"original": corr.original, "corrected": corr.corrected}],
                )
                db.add(pattern)
                new_patterns.append(pattern)

        await db.flush()
        return new_patterns

    async def get_learner_context(
        self,
        db: AsyncSession,
        learner_id: str,
        agent_id: str,
    ) -> str:
        """Build a context string summarizing the learner's current state for the LLM.

        This gets injected into the system prompt so the tutor knows where the learner is.
        """
        # Get mastery records
        stmt = select(Mastery, Concept).join(Concept, Mastery.concept_id == Concept.id).where(
            Mastery.learner_id == learner_id
        ).order_by(Mastery.p_mastery)
        rows = (await db.execute(stmt)).all()

        if not rows:
            return "No prior learning data. This is a new learner."

        lines = ["Learner knowledge state:"]
        weak = []
        strong = []
        for mastery, concept in rows:
            pct = f"{mastery.p_mastery:.0%}"
            if mastery.p_mastery < 0.5:
                weak.append(f"  {concept.name}: {pct} ({mastery.interactions_count} attempts)")
            elif mastery.p_mastery > 0.8:
                strong.append(f"  {concept.name}: {pct}")

        if weak:
            lines.append("WEAK AREAS (focus here):")
            lines.extend(weak[:10])
        if strong:
            lines.append(f"\nMASTERED ({len(strong)} concepts): {', '.join(s.split(':')[0] for s in strong[:5])}")

        return "\n".join(lines)


# Singleton
kg_engine = KnowledgeGraphEngine()
