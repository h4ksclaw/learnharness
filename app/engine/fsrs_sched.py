"""FSRS spaced repetition scheduling.

Wraps the py-fsrs library. Each concept the learner struggles with becomes
a review item that FSRS schedules for optimal recall.
"""

from datetime import datetime, timezone

from fsrs import Scheduler, Card, Rating, State

from app.config import settings
from app.models import ReviewItem


class FSRSScheduler:
    """Manages review scheduling using the FSRS algorithm."""

    def __init__(self, target_retention: float | None = None):
        self.target_retention = target_retention or settings.fsrs_target_retention
        self.fsrs = Scheduler()

    def schedule_new(self, concept_id: str, content: dict, learner_id: str) -> ReviewItem:
        """Create a new review item for a concept."""
        now = datetime.now(timezone.utc)
        # Start with a fresh card to get initial scheduling
        card = Card()
        return ReviewItem(
            learner_id=learner_id,
            concept_id=concept_id,
            content=content,
            stability=0.0,
            difficulty=0.0,
            elapsed_days=0.0,
            scheduled_days=0.0,
            reps=0,
            lapses=0,
            state=1,  # Learning (py-fsrs has no "New" state, starts at Learning)
            last_review=None,
            next_review=now,
        )

    def review(self, item: ReviewItem, rating: int) -> ReviewItem:
        """Apply a review to an item and reschedule.

        Args:
            item: The review item to update
            rating: 1=again, 2=hard, 3=good, 4=easy

        Returns:
            The updated item (caller must commit to DB)
        """
        fsrs_rating = Rating(rating)
        now = datetime.now(timezone.utc)

        # Reconstruct FSRS Card from our stored state
        # Map our DB state to FSRS State enum
        state_map = {1: State.Learning, 2: State.Review, 3: State.Relearning}
        fsrs_state = state_map.get(item.state, State.Learning)

        card = Card(
            state=fsrs_state,
            stability=item.stability if item.stability > 0 else None,
            difficulty=item.difficulty if item.difficulty > 0 else None,
            due=item.next_review,
            last_review=item.last_review,
        )

        # Schedule the review
        updated_card, _review_log = self.fsrs.review_card(card, fsrs_rating, now)

        # Write back to our item
        item.stability = updated_card.stability or 0.0
        item.difficulty = updated_card.difficulty or 0.0
        item.reps += 1
        if fsrs_rating == Rating.Again:
            item.lapses += 1
        item.state = int(updated_card.state)
        item.elapsed_days = (now - item.last_review).days if item.last_review else 0
        item.last_review = now
        item.next_review = updated_card.due or now

        return item

    def is_due(self, item: ReviewItem, now: datetime | None = None) -> bool:
        """Check if a review item is due."""
        now = now or datetime.now(timezone.utc)
        return item.next_review <= now


# Singleton
fsrs_scheduler = FSRSScheduler()
