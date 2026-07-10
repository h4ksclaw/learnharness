"""Chat router — OpenAI-compatible endpoint with learning intelligence."""

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.harness import agent_harness
from app.schemas import ChatRequest
from app.schemas import ChatResponse

router = APIRouter()


@router.post("/v1/chat/completions", response_model=ChatResponse)
async def chat_completions(request: ChatRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    """OpenAI-compatible chat with transparent learning analysis."""
    return await agent_harness.process_message(db, request)
