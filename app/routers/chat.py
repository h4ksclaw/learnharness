"""Chat router — OpenAI-compatible endpoint with learning intelligence."""

import time

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.harness import agent_harness
from app.db import get_db
from app.schemas import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/v1/chat/completions", response_model=ChatResponse)
async def chat_completions(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """OpenAI-compatible chat completions with transparent learning analysis.

    Standard OpenAI clients work out of the box. The learning logic
    (concept extraction, mastery tracking, corrections) runs silently
    and attaches extra fields to the response.
    """
    return await agent_harness.process_message(db, request)
