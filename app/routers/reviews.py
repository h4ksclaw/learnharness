"""Reviews router — FSRS spaced repetition."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.engine.fsrs_sched import fsrs_scheduler
from app.models import ReviewItem
from app.schemas import ReviewItemOut, ReviewAnswer

router = APIRouter()


@router.get("/v1/reviews/{learner_id}", response_model=list[ReviewItemOut])
async def get_due_reviews(learner_id: str, db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    stmt = select(ReviewItem).where(
        ReviewItem.learner_id == learner_id,
        ReviewItem.next_review <= now,
    ).order_by(ReviewItem.next_review)
    return (await db.execute(stmt)).scalars().all()


@router.post("/v1/reviews/{review_id}/answer", response_model=ReviewItemOut)
async def answer_review(review_id: int, answer: ReviewAnswer, db: AsyncSession = Depends(get_db)):
    item = (await db.execute(select(ReviewItem).where(ReviewItem.id == review_id))).scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Review item not found")
    updated = fsrs_scheduler.review(item, answer.rating)
    await db.commit()
    await db.refresh(updated)
    return updated


@router.get("/v1/reviews/{learner_id}/all", response_model=list[ReviewItemOut])
async def get_all_reviews(learner_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(ReviewItem).where(ReviewItem.learner_id == learner_id).order_by(ReviewItem.next_review)
    return (await db.execute(stmt)).scalars().all()
