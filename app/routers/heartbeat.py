"""Outbound messages and heartbeat endpoints.

Channel adapters poll /v1/outbound to pick up messages the agent wants to send.
"""

from datetime import UTC
from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import OutboundMessage
from app.schemas import OutboundMessageOut

router = APIRouter()


@router.get("/v1/outbound", response_model=list[OutboundMessageOut])
async def get_pending_outbound(
    db: Annotated[AsyncSession, Depends(get_db)],
    channel: str | None = None,
    agent_id: str | None = None,
):
    """Get unsent outbound messages. Channel adapters poll this."""
    stmt = select(OutboundMessage).where(OutboundMessage.sent == False)  # noqa: E712
    if channel:
        stmt = stmt.where((OutboundMessage.channel == channel) | (OutboundMessage.channel == "all"))
    if agent_id:
        stmt = stmt.where(OutboundMessage.agent_id == agent_id)
    stmt = stmt.order_by(OutboundMessage.created_at).limit(50)
    return (await db.execute(stmt)).scalars().all()


@router.post("/v1/outbound/{message_id}/sent", status_code=204)
async def mark_sent(message_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    """Mark an outbound message as sent."""
    from datetime import datetime

    msg = (
        await db.execute(select(OutboundMessage).where(OutboundMessage.id == message_id))
    ).scalar_one_or_none()
    if msg:
        msg.sent = True
        msg.sent_at = datetime.now(UTC)
        await db.commit()
