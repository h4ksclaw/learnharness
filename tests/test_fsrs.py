"""Test FSRS scheduling."""

from datetime import datetime, timezone, timedelta

from app.engine.fsrs_sched import FSRSScheduler
from app.models import ReviewItem


def test_new_item_creation():
    sched = FSRSScheduler()
    item = sched.schedule_new(
        concept_id="test-concept",
        content={"front": "Hallo", "back": "Hello"},
        learner_id="learner-1",
    )
    assert item.concept_id == "test-concept"
    assert item.reps == 0


def test_review_increases_reps():
    sched = FSRSScheduler()
    item = sched.schedule_new(
        concept_id="c1",
        content={"front": "danke", "back": "thank you"},
        learner_id="l1",
    )
    item = sched.review(item, rating=3)  # good
    assert item.reps == 1
    assert item.last_review is not None
    assert item.stability > 0  # FSRS assigns stability after first review


def test_again_increases_lapses():
    sched = FSRSScheduler()
    item = sched.schedule_new(
        concept_id="c1",
        content={"front": "danke", "back": "thank you"},
        learner_id="l1",
    )
    # First review as good to get into review state
    item = sched.review(item, rating=3)
    lapses_before = item.lapses
    # Then fail it
    item = sched.review(item, rating=1)  # again
    assert item.lapses == lapses_before + 1


def test_is_due():
    sched = FSRSScheduler()
    now = datetime.now(timezone.utc)

    # Item scheduled in the past → due
    item = ReviewItem(
        id=1, learner_id="l1", concept_id="c1", content={},
        next_review=now - timedelta(hours=1),
    )
    assert sched.is_due(item, now)

    # Item scheduled in the future → not due
    item = ReviewItem(
        id=2, learner_id="l1", concept_id="c1", content={},
        next_review=now + timedelta(days=3),
    )
    assert not sched.is_due(item, now)
