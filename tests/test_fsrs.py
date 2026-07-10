"""Test FSRS scheduling."""

from datetime import datetime, timezone, timedelta

from app.engine.fsrs_sched import FSRSScheduler
from app.models import ReviewItem


def test_new_item():
    sched = FSRSScheduler()
    item = sched.schedule_new("c1", {"front": "Hallo", "back": "Hello"}, "l1")
    assert item.concept_id == "c1"
    assert item.reps == 0


def test_review_good():
    sched = FSRSScheduler()
    item = sched.schedule_new("c1", {"front": "danke", "back": "thank you"}, "l1")
    item = sched.review(item, rating=3)
    assert item.reps == 1
    assert item.stability > 0


def test_again_increases_lapses():
    sched = FSRSScheduler()
    item = sched.schedule_new("c1", {}, "l1")
    item = sched.review(item, rating=3)
    before = item.lapses
    item = sched.review(item, rating=1)
    assert item.lapses == before + 1


def test_is_due():
    sched = FSRSScheduler()
    now = datetime.now(timezone.utc)
    item = ReviewItem(
        id=1, learner_id="l1", concept_id="c1", content={},
        next_review=now - timedelta(hours=1),
    )
    assert sched.is_due(item, now)

    item.next_review = now + timedelta(days=3)
    assert not sched.is_due(item, now)
