"""Chat router — OpenAI-compatible endpoint with learning intelligence."""

from typing import Annotated
from typing import Any

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.harness import agent_harness
from app.schemas import ChatMessage
from app.schemas import ChatRequest
from app.schemas import ChatResponse

router = APIRouter()


@router.post("/v1/chat/completions", response_model=ChatResponse)
async def chat_completions(request: ChatRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    """OpenAI-compatible chat with transparent learning analysis."""
    return await agent_harness.process_message(db, request)


@router.post("/v1/responses")
async def responses_compat(
    raw_request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Compatibility shim: translate OpenAI Responses API calls to our chat handler.

    CopilotKit's OpenAIAdapter uses @ai-sdk/openai which defaults to the
    Responses API (/v1/responses). This endpoint accepts that format and
    forwards it to our standard /v1/chat/completions handler.
    """
    body: dict[str, Any] = await raw_request.json()

    # Extract messages from Responses API input format
    input_data = body.get("input", [])
    messages: list[ChatMessage] = []

    # Responses API sends instructions as a top-level field
    instructions = body.get("instructions")
    if instructions:
        messages.append(ChatMessage(role="system", content=instructions))

    for item in input_data:
        if isinstance(item, str):
            messages.append(ChatMessage(role="user", content=item))
        elif isinstance(item, dict):
            role = item.get("role", "user")
            content = item.get("content", "")
            # Handle content arrays
            if isinstance(content, list):
                content = " ".join(
                    c.get("text", "") if isinstance(c, dict) else str(c) for c in content
                )
            messages.append(ChatMessage(role=role, content=content))

    chat_request = ChatRequest(
        messages=messages,
        stream=body.get("stream", False),
        temperature=body.get("temperature"),
        max_tokens=body.get("max_output_tokens"),
        agent_id=body.get("agent_id"),
    )

    # If no agent_id, pick the first available agent
    if not chat_request.agent_id:
        from sqlalchemy import select

        from app.models import Agent

        stmt = select(Agent).where(Agent.active).limit(1)
        agent = (await db.execute(stmt)).scalar_one_or_none()
        if agent:
            chat_request.agent_id = agent.id

    result = await agent_harness.process_message(db, chat_request)

    # Return in Responses API format
    assistant_content = result.choices[0].message.content if result.choices else ""
    return {
        "id": result.id,
        "object": "response",
        "created_at": result.created,
        "model": result.model,
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": assistant_content}],
            }
        ],
        "usage": {
            "input_tokens": result.usage.prompt_tokens,
            "output_tokens": result.usage.completion_tokens,
            "total_tokens": result.usage.total_tokens,
        },
    }
