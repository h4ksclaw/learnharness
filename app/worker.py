"""Background worker — heartbeat scheduler.

Runs as a separate container (from compose.yaml). Checks all active agents
on their configured heartbeat interval and generates proactive messages:
- Review reminders (FSRS items due)
- Inactivity check-ins
- Weak-spot focus suggestions

Messages are written to outbound_messages table. Channel adapters pick them up.
"""

import asyncio
import logging
from datetime import UTC
from datetime import datetime

from sqlalchemy import select

from app.db import async_session
from app.models import Agent
from app.models import Concept
from app.models import Interaction
from app.models import Learner
from app.models import Mastery
from app.models import OutboundMessage
from app.models import ReviewItem

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("learnharness.worker")


async def check_heartbeat(agent: Agent) -> list[OutboundMessage]:
    """Check if any learner on this agent needs proactive contact.

    Returns a list of OutboundMessage objects to create.
    """
    messages = []
    now = datetime.now(UTC)

    async with async_session() as db:
        # Get all learners for this agent
        stmt = select(Learner).where(Learner.agent_id == agent.id)
        learners = (await db.execute(stmt)).scalars().all()

        for learner in learners:
            # Check FSRS reviews due
            review_stmt = select(ReviewItem).where(
                ReviewItem.learner_id == learner.id,
                ReviewItem.next_review <= now,
            )
            due_reviews = (await db.execute(review_stmt)).scalars().all()

            if due_reviews:
                # Get concept names for due reviews
                concept_ids = list({r.concept_id for r in due_reviews})
                concept_stmt = select(Concept).where(Concept.id.in_(concept_ids))
                concepts = (await db.execute(concept_stmt)).scalars().all()
                concept_names = [c.name for c in concepts[:3]]

                messages.append(
                    OutboundMessage(
                        agent_id=agent.id,
                        learner_id=learner.id,
                        channel="all",
                        message=(
                            f"Hey {learner.name}! You have {len(due_reviews)} "
                            f"review{'s' if len(due_reviews) != 1 else ''} due"
                            f" ({', '.join(concept_names)}). Ready for a quick check?"
                        ),
                        metadata={
                            "type": "review_reminder",
                            "review_ids": [r.id for r in due_reviews],
                        },
                    )
                )
                continue

            # Check inactivity
            if learner.last_active:
                inactive_hours = (now - learner.last_active).total_seconds() / 3600
                if inactive_hours > 24:
                    messages.append(
                        OutboundMessage(
                            agent_id=agent.id,
                            learner_id=learner.id,
                            channel="all",
                            message=(
                                f"Hey {learner.name}! It's been {int(inactive_hours)}h "
                                f"since we last chatted. Want to continue?"
                            ),
                            metadata={"type": "inactivity", "inactive_hours": inactive_hours},
                        )
                    )
                    continue

            # Check weak spots
            weak_stmt = (
                select(Mastery, Concept)
                .join(Concept, Mastery.concept_id == Concept.id)
                .where(Mastery.learner_id == learner.id, Mastery.p_mastery < 0.4)
                .order_by(Mastery.p_mastery)
                .limit(1)
            )
            weak = (await db.execute(weak_stmt)).first()
            if weak:
                mastery, concept = weak
                messages.append(
                    OutboundMessage(
                        agent_id=agent.id,
                        learner_id=learner.id,
                        channel="all",
                        message=(
                            f"I noticed you're still working on '{concept.name}' "
                            f"({mastery.p_mastery:.0%} mastery). Want to practice?"
                        ),
                        metadata={
                            "type": "weak_spot",
                            "concept_id": concept.id,
                            "mastery": mastery.p_mastery,
                        },
                    )
                )

    return messages


async def run_worker():
    """Main worker loop — runs forever."""
    log.info("LearnHarness worker started")

    while True:
        try:
            async with async_session() as db:
                # Get all active agents with heartbeat > 0
                stmt = select(Agent).where(
                    Agent.active == True,  # noqa: E712
                    Agent.heartbeat_interval > 0,
                )
                agents = (await db.execute(stmt)).scalars().all()

                for agent in agents:
                    # Check if enough time has passed since last heartbeat for this agent
                    # Look for the most recent heartbeat interaction
                    last_hb_stmt = (
                        select(Interaction)
                        .where(Interaction.agent_id == agent.id, Interaction.type == "heartbeat")
                        .order_by(Interaction.created_at.desc())
                        .limit(1)
                    )
                    last_hb = (await db.execute(last_hb_stmt)).scalar_one_or_none()

                    now = datetime.now(UTC)
                    should_check = True
                    if last_hb:
                        elapsed = (now - last_hb.created_at).total_seconds()
                        should_check = elapsed >= agent.heartbeat_interval

                    if should_check:
                        messages = await check_heartbeat(agent)
                        for msg in messages:
                            db.add(msg)
                        if messages:
                            log.info(
                                "Agent '%s' generated %d heartbeat message(s)",
                                agent.name,
                                len(messages),
                            )

                        # Record heartbeat check
                        db.add(
                            Interaction(
                                learner_id=None,
                                agent_id=agent.id,
                                session_id="heartbeat",
                                type="heartbeat",
                                user_input="",
                                agent_response="",
                                tool_calls=[],
                            )
                        )
                        await db.commit()

        except Exception as e:
            log.error("Worker error: %s", e, exc_info=True)

        # Sleep between checks (check every 60s, per-agent interval is checked above)
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(run_worker())
