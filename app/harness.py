"""Agent harness — the main execution loop.

Pipeline:
1. Analyze user message → extract concepts, corrections, mastery signals
2. Update knowledge graph + BKT mastery
3. Build enriched system prompt with learner context
4. Call LLM (with tools if enabled) — handles tool-call loops
5. Return response + corrections + deltas
"""

import json
import time
import uuid
from datetime import UTC
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.knowledge_graph import kg_engine
from app.engine.llm import llm_router
from app.models import Agent
from app.models import Concept
from app.models import Interaction
from app.models import Learner
from app.models import ReviewItem
from app.schemas import ChatMessage
from app.schemas import ChatRequest
from app.schemas import ChatResponse
from app.schemas import ChatResponseChoice
from app.schemas import ChatResponseUsage
from app.schemas import Correction
from app.schemas import MasteryDelta
from app.tools import execute_tool
from app.tools import get_openai_tool_schemas


class AgentHarness:
    """Main agent execution harness."""

    async def process_message(self, db: AsyncSession, request: ChatRequest) -> ChatResponse:
        agent = await self._get_agent(db, request.agent_id)
        learner = await self._get_or_create_learner(db, request.learner_id, agent.id)

        user_messages = [m for m in request.messages if m.role == "user"]
        if not user_messages:
            return self._error_response("No user message found")
        user_text = user_messages[-1].content

        # ─── Phase 1: Analyze ───
        existing_concepts = await self._get_concept_names(db, agent.id)
        analysis = await kg_engine.analyze_message(
            user_message=user_text,
            master_prompt=agent.master_prompt,
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
        system_prompt = f"{agent.master_prompt}\n\n---\n{learner_context}"

        # ─── Phase 4: Call LLM (with tools) ───
        messages_for_llm = [{"role": "system", "content": system_prompt}]
        for msg in request.messages:
            messages_for_llm.append({"role": msg.role, "content": msg.content})

        tool_calls_made = []
        if agent.tools:
            tool_schemas = get_openai_tool_schemas(agent.tools)
            llm_result = await self._llm_with_tools(messages_for_llm, tool_schemas, agent, request)
            tool_calls_made = llm_result.get("tool_calls_made", [])
        else:
            llm_result = await llm_router.complete(
                messages=messages_for_llm,
                model=agent.llm_model or request.model,
                temperature=request.temperature or 0.7,
                max_tokens=request.max_tokens,
            )

        content = llm_result["content"]

        # ─── Phase 5: Build response ───
        corrections = [
            Correction(
                original=c.original,
                corrected=c.corrected,
                rule=c.rule,
                concept_id=concept_map[c.concept_name].id
                if c.concept_name and c.concept_name in concept_map
                else None,
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

        due_reviews = await self._get_due_reviews(db, learner.id)

        # ─── Phase 6: Persist ───
        interaction = Interaction(
            learner_id=learner.id,
            agent_id=agent.id,
            session_id=request.session_id or str(uuid.uuid4()),
            type="chat",
            user_input=user_text,
            agent_response=content,
            concept_ids=[c.id for c in concept_map.values()],
            corrections=[c.model_dump() for c in corrections],
            mastery_deltas=dict(mastery_deltas),
            tool_calls=tool_calls_made,
        )
        db.add(interaction)
        learner.last_active = datetime.now(UTC)
        await db.commit()

        return ChatResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:24]}",
            created=int(time.time()),
            model=llm_result.get("model", "unknown"),
            choices=[
                ChatResponseChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=content),
                    finish_reason="stop",
                )
            ],
            usage=ChatResponseUsage(**llm_result.get("usage", {})),
            corrections=corrections,
            mastery_deltas=m_deltas,
            concepts_detected=list(concept_map.keys()),
            reviews_due=due_reviews,
            tool_calls=tool_calls_made,
        )

    async def _llm_with_tools(
        self,
        messages: list[dict],
        tool_schemas: list[dict],
        agent: Agent,
        request: ChatRequest,
    ) -> dict:
        """Call LLM with tools, handling tool-call loops."""
        import httpx

        model = agent.llm_model or request.model or None
        headers = {"Content-Type": "application/json"}
        if llm_router.api_key and llm_router.api_key != "not-needed":
            headers["Authorization"] = f"Bearer {llm_router.api_key}"

        payload = {
            "model": model or llm_router.default_model,
            "messages": messages,
            "temperature": request.temperature or 0.7,
            "tools": tool_schemas,
        }
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens

        tool_calls_made = []
        async with httpx.AsyncClient(timeout=120) as client:
            for _ in range(5):  # max 5 tool-call rounds
                resp = await client.post(
                    f"{llm_router.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

                msg = data["choices"][0]["message"]

                if not msg.get("tool_calls"):
                    # No more tool calls — return final response
                    return {
                        "content": msg["content"],
                        "model": data.get("model", model),
                        "usage": data.get("usage", {}),
                        "tool_calls_made": tool_calls_made,
                    }

                # Execute tool calls
                payload["messages"].append(msg)

                for tc in msg["tool_calls"]:
                    fn_name = tc["function"]["name"]
                    fn_args = json.loads(tc["function"]["arguments"])

                    result = await execute_tool(fn_name, fn_args)
                    tool_calls_made.append(
                        {
                            "tool": fn_name,
                            "args": fn_args,
                            "result": str(result)[:1000],
                        }
                    )

                    payload["messages"].append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": json.dumps(result, default=str)[:5000],
                        }
                    )

            # Max rounds reached — get final response without tools
            payload.pop("tools", None)
            resp = await client.post(
                f"{llm_router.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "content": data["choices"][0]["message"]["content"],
                "model": data.get("model", model),
                "usage": data.get("usage", {}),
                "tool_calls_made": tool_calls_made,
            }

    async def _get_agent(self, db: AsyncSession, agent_id: str | None) -> Agent:
        if agent_id:
            stmt = select(Agent).where(Agent.id == agent_id)
            agent = (await db.execute(stmt)).scalar_one_or_none()
            if agent:
                return agent
        stmt = select(Agent).where(Agent.active == True).limit(1)  # noqa: E712
        agent = (await db.execute(stmt)).scalar_one_or_none()
        if agent:
            return agent
        raise ValueError("No agent found. Create one via POST /v1/agents")

    async def _get_or_create_learner(
        self, db: AsyncSession, learner_id: str | None, agent_id: str
    ) -> Learner:
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
        now = datetime.now(UTC)
        stmt = (
            select(ReviewItem)
            .where(
                ReviewItem.learner_id == learner_id,
                ReviewItem.next_review <= now,
            )
            .limit(5)
        )
        items = (await db.execute(stmt)).scalars().all()
        return [
            {"id": i.id, "concept_id": i.concept_id, "next_review": i.next_review.isoformat()}
            for i in items
        ]

    def _error_response(self, message: str) -> ChatResponse:
        return ChatResponse(
            id=f"chatcmpl-err-{uuid.uuid4().hex[:8]}",
            created=int(time.time()),
            model="error",
            choices=[
                ChatResponseChoice(
                    message=ChatMessage(role="assistant", content=f"Error: {message}"),
                    finish_reason="error",
                )
            ],
        )


agent_harness = AgentHarness()
