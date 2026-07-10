"""Proactive scheduler — the agent's 'heartbeat'.

Runs on a configurable interval and checks:
1. Are any FSRS review items due? → Push a reminder
2. Has the learner been inactive? → Initiate contact
3. Are there weak concepts that need attention? → Suggest a mini-session

The scheduler is intentionally backend-only. It emits events/notifications
that any frontend (IRC bot, Telegram, push notification) can consume.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Agent, Learner, ReviewItem, Mastery, Concept


class HeartbeatAction(str, Enum):
    REVIEW_REMINDER = "review_reminder"
    INACTIVE_CHECKIN = "inactive_checkin"
    WEAK_SPOT_FOCUS = "weak_spot_focus"
    NONE = "none"


@dataclass
class HeartbeatResult:
    """Result of a heartbeat check for a single learner."""
    action: HeartbeatAction
    learner_id: str
    agent_id: str
    message: str
    data: dict


class ProactiveScheduler:
    """Checks learner state and generates proactive actions."""

    async def check_learner(
        self,
        db: AsyncSession,
        learner: Learner,
        agent: Agent,
    ) -> HeartbeatResult:
        """Run heartbeat check for a single learner."""
        now = datetime.now(timezone.utc)

        # Skip if agent isn't proactive
        if not agent.proactive:
            return HeartbeatResult(
                action=HeartbeatAction.NONE,
                learner_id=learner.id,
                agent_id=agent.id,
                message="",
                data={},
            )

        # 1. Check for due reviews
        due = await self._get_due_reviews(db, learner.id, now)
        if due:
            concept_names = await self._get_concept_names_by_ids(db, [d.concept_id for d in due])
            names_str = ", ".join(concept_names[:3])
            return HeartbeatResult(
                action=HeartbeatAction.REVIEW_REMINDER,
                learner_id=learner.id,
                agent_id=agent.id,
                message=f"Hey! You have {len(due)} review{'s' if len(due)==1 else ''} due ({names_str}). Ready for a quick check?",
                data={
                    "review_ids": [d.id for d in due],
                    "concept_names": concept_names,
                    "count": len(due),
                },
            )

        # 2. Check inactivity
        if learner.last_active:
            inactive_hours = (now - learner.last_active).total_seconds() / 3600
            if inactive_hours > 24:
                return HeartbeatResult(
                    action=HeartbeatAction.INACTIVE_CHECKIN,
                    learner_id=learner.id,
                    agent_id=agent.id,
                    message=f"Hey {learner.name}! It's been {int(inactive_hours)}h since we last chatted. Want to practice some {agent.domain}?",
                    data={"inactive_hours": inactive_hours},
                )

        # 3. Check weak spots
        weak = await self._get_weakest_concept(db, learner.id)
        if weak and weak.p_mastery < 0.3:
            return HeartbeatResult(
                action=HeartbeatAction.WEAK_SPOT_FOCUS,
                learner_id=learner.id,
                agent_id=agent.id,
                message=f"I noticed you're still working on '{weak_name}'. Want to do a quick exercise?",
                data={"concept_id": weak.concept_id, "mastery": weak.p_mastery},
            )

        return HeartbeatResult(
            action=HeartbeatAction.NONE,
            learner_id=learner.id,
            agent_id=agent.id,
            message="",
            data={},
        )

    async def check_all(self, db: AsyncSession) -> list[HeartbeatResult]:
        """Run heartbeat for all proactive learners."""
        stmt = (
            select(Learner, Agent)
            .join(Agent, Learner.agent_id == Agent.id)
            .where(Agent.proactive == True)
        )
        rows = (await db.execute(stmt)).all()
        results = []
        for learner, agent in rows:
            result = await self.check_learner(db, learner, agent)
            if result.action != HeartbeatAction.NONE:
                results.append(result)
        return results

    async def _get_due_reviews(
        self, db: AsyncSession, learner_id: str, now: datetime
    ) -> list[ReviewItem]:
        stmt = select(ReviewItem).where(
            ReviewItem.learner_id == learner_id,
            ReviewItem.next_review <= now,
        ).limit(5)
        return list((await db.execute(stmt)).scalars().all())

    async def _get_concept_names_by_ids(
        self, db: AsyncSession, concept_ids: list[str]
    ) -> list[str]:
        if not concept_ids:
            return []
        stmt = select(Concept.name).where(Concept.id.in_(concept_ids))
        return list((await db.execute(stmt)).scalars().all())

    async def _get_weakest_concept(
        self, db: AsyncSession, learner_id: str
    ) -> Mastery | None:
        stmt = select(Mastery).where(
            Mastery.learner_id == learner_id
        ).order_by(Mastery.p_mastery).limit(1)
        return (await db.execute(stmt)).scalar_one_or_none()


# Singleton
proactive_scheduler = ProactiveScheduler()
