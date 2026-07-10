"""Agent harness — the main execution loop that ties everything together.

This is the "brain" that processes a chat message through the full pipeline:
1. Analyze message → extract concepts, errors, mastery signals
2. Update knowledge graph + mastery state
3. Build enriched system prompt with learner context
4. Call LLM for response
5. Return response with corrections and metadata
"""

import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.persona import build_system_prompt, PersonaConfig
from app.engine.knowledge_graph import kg_engine, AnalysisResult
from app.engine.knowledge_tracing import knowledge_tracer
from app.engine.llm import llm_router
from app.engine.fsrs_sched import fsrs_scheduler
from app.models import Agent, Learner, Interaction, Concept, Mastery, ReviewItem
from app.schemas import (
    ChatRequest, ChatResponse, ChatResponseChoice, ChatMessage,
    Correction, MasteryDelta, ChatResponseUsage,
)


class AgentHarness:
    """The main agent execution harness."""

    async def process_message(
        self,
        db: AsyncSession,
        request: ChatRequest,
    ) -> ChatResponse:
        """Process a chat message through the full learning pipeline."""
        # Resolve agent and learner
        agent = await self._get_agent(db, request.agent_id)
        learner = await self._get_or_create_learner(db, request.learner_id, agent.id)

        # Get user's latest message
        user_messages = [m for m in request.messages if m.role == "user"]
        if not user_messages:
            return self._error_response("No user message found")
        user_text = user_messages[-1].content

        # ─── Phase 1: Analyze ───
        existing_concepts = await self._get_concept_names(db, agent.id)
        analysis = AnalysisResult()
        if request.analyze:
            analysis = await kg_engine.analyze_message(
                user_message=user_text,
                agent_domain=agent.domain,
                agent_level=agent.level,
                target_language=agent.target_language,
                existing_concepts=existing_concepts,
            )

        # ─── Phase 2: Update knowledge graph ───
        concept_map = await kg_engine.upsert_concepts(db, agent.id, analysis.concepts)
        await kg_engine.add_edges(db, concept_map, analysis.edges)
        mastery_deltas = await kg_engine.update_mastery(
            db, learner.id, concept_map, analysis.mastery_signals
        )
        await kg_engine.record_errors(db, learner.id, concept_map, analysis.corrections)

        # ─── Phase 3: Build enriched system prompt ───
        learner_context = await kg_engine.get_learner_context(db, learner.id, agent.id)
        system_prompt = f"{agent.system_prompt}\n\n---\n{learner_context}"

        # ─── Phase 4: Call LLM ───
        messages_for_llm = [{"role": "system", "content": system_prompt}]
        for msg in request.messages:
            messages_for_llm.append({"role": msg.role, "content": msg.content})

        llm_result = await llm_router.complete(
            messages=messages_for_llm,
            model=agent.llm_model or request.model,
            temperature=request.temperature or 0.7,
            max_tokens=request.max_tokens,
        )

        # ─── Phase 5: Build response ───
        corrections = [
            Correction(
                original=c.original,
                corrected=c.corrected,
                rule=c.rule,
                concept_id=concept_map[c.concept_name].id if c.concept_name and c.concept_name in concept_map else None,
                severity=c.severity,
            )
            for c in analysis.corrections
        ]

        m_deltas = [
            MasteryDelta(
                concept_id=d["concept_id"],
                concept_name=name,
                before=d["before"],
                after=d["after"],
                direction="up" if d["delta"] > 0.01 else ("down" if d["delta"] < -0.01 else "same"),
            )
            for name, d in mastery_deltas.items()
        ]

        # Check for due reviews
        due_reviews = await self._get_due_reviews(db, learner.id)

        # ─── Phase 6: Persist interaction ───
        interaction = Interaction(
            learner_id=learner.id,
            agent_id=agent.id,
            session_id=request.session_id or str(uuid.uuid4()),
            type="chat",
            user_input=user_text,
            agent_response=llm_result["content"],
            concept_ids=[c.id for c in concept_map.values()],
            corrections=[c.model_dump() for c in corrections],
            mastery_deltas={name: d for name, d in mastery_deltas.items()},
        )
        db.add(interaction)

        # Update learner last_active
        learner.last_active = datetime.now(timezone.utc)

        await db.commit()

        # ─── Phase 7: Return ───
        return ChatResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:24]}",
            created=int(time.time()),
            model=llm_result["model"],
            choices=[ChatResponseChoice(
                index=0,
                message=ChatMessage(role="assistant", content=llm_result["content"]),
                finish_reason="stop",
            )],
            usage=ChatResponseUsage(**llm_result.get("usage", {})),
            corrections=corrections,
            mastery_deltas=m_deltas,
            concepts_detected=list(concept_map.keys()),
            reviews_due=due_reviews,
        )

    async def _get_agent(self, db: AsyncSession, agent_id: str | None) -> Agent:
        if agent_id:
            stmt = select(Agent).where(Agent.id == agent_id)
            agent = (await db.execute(stmt)).scalar_one_or_none()
            if agent:
                return agent
        # Default: first agent
        stmt = select(Agent).limit(1)
        agent = (await db.execute(stmt)).scalar_one_or_none()
        if agent:
            return agent
        raise ValueError("No agent found. Create an agent first via POST /v1/agents")

    async def _get_or_create_learner(self, db: AsyncSession, learner_id: str | None, agent_id: str) -> Learner:
        if learner_id:
            stmt = select(Learner).where(Learner.id == learner_id)
            learner = (await db.execute(stmt)).scalar_one_or_none()
            if learner:
                return learner

        learner = Learner(id=learner_id or str(uuid.uuid4()), agent_id=agent_id)
        db.add(learner)
        await db.flush()
        return learner

    async def _get_concept_names(self, db: AsyncSession, agent_id: str) -> list[str]:
        stmt = select(Concept.name).where(Concept.agent_id == agent_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def _get_due_reviews(self, db: AsyncSession, learner_id: str) -> list[dict]:
        now = datetime.now(timezone.utc)
        stmt = select(ReviewItem).where(
            ReviewItem.learner_id == learner_id,
            ReviewItem.next_review <= now,
        ).limit(5)
        items = (await db.execute(stmt)).scalars().all()
        return [{"id": i.id, "concept_id": i.concept_id, "next_review": i.next_review.isoformat()} for i in items]

    def _error_response(self, message: str) -> ChatResponse:
        return ChatResponse(
            id=f"chatcmpl-err-{uuid.uuid4().hex[:8]}",
            created=int(time.time()),
            model="error",
            choices=[ChatResponseChoice(
                message=ChatMessage(role="assistant", content=f"Error: {message}"),
                finish_reason="error",
            )],
        )


# Singleton
agent_harness = AgentHarness()
