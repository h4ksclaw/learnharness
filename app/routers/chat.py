"""Chat router — OpenAI-compatible endpoint with learning intelligence."""

import json
import time
import uuid
from typing import Annotated
from typing import Any

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Request
from fastapi.responses import StreamingResponse
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


def _sse_event(event_type: str, data: dict[str, Any]) -> str:
    """Format a Server-Sent Events message."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


async def _resolve_agent_id(db: AsyncSession, agent_id: str | None) -> str | None:
    """Pick the first active agent if none specified."""
    if agent_id:
        return agent_id
    from sqlalchemy import select

    from app.models import Agent

    stmt = select(Agent).where(Agent.active).limit(1)
    agent = (await db.execute(stmt)).scalar_one_or_none()
    return agent.id if agent else None


def _parse_responses_input(body: dict[str, Any]) -> list[ChatMessage]:
    """Convert Responses API input format to ChatMessage list."""
    input_data = body.get("input", [])
    messages: list[ChatMessage] = []

    instructions = body.get("instructions")
    if instructions:
        messages.append(ChatMessage(role="system", content=instructions))

    for item in input_data:
        if isinstance(item, str):
            messages.append(ChatMessage(role="user", content=item))
        elif isinstance(item, dict):
            role = item.get("role", "user")
            content = item.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    c.get("text", "") if isinstance(c, dict) else str(c) for c in content
                )
            messages.append(ChatMessage(role=role, content=content))
    return messages


@router.post("/v1/responses")
async def responses_compat(
    raw_request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Compatibility shim: translate OpenAI Responses API calls to our chat handler.

    CopilotKit's OpenAIAdapter uses @ai-sdk/openai which defaults to the
    Responses API (/v1/responses). This endpoint accepts that format and
    forwards it to our standard /v1/chat/completions handler, then wraps
    the result in the SSE streaming format that @ai-sdk/openai expects.
    """
    body: dict[str, Any] = await raw_request.json()
    messages = _parse_responses_input(body)
    agent_id = await _resolve_agent_id(db, body.get("agent_id"))

    chat_request = ChatRequest(
        messages=messages,
        stream=False,
        temperature=body.get("temperature"),
        max_tokens=body.get("max_output_tokens"),
        agent_id=agent_id,
    )

    wants_stream = body.get("stream", True)

    if not wants_stream:
        # Non-streaming: return plain JSON
        result = await agent_harness.process_message(db, chat_request)
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

    # Streaming: return SSE in the format @ai-sdk/openai expects
    response_id = f"resp_{uuid.uuid4().hex[:24]}"
    created_at = int(time.time())

    async def generate_sse() -> Any:
        try:
            # 1. response.created
            yield _sse_event(
                "response.created",
                {
                    "type": "response.created",
                    "response": {
                        "id": response_id,
                        "object": "response",
                        "created_at": created_at,
                        "status": "in_progress",
                        "model": "",
                        "output": [],
                    },
                },
            )

            # 2. response.output_item.added (message container)
            item_id = f"msg_{uuid.uuid4().hex[:24]}"
            yield _sse_event(
                "response.output_item.added",
                {
                    "type": "response.output_item.added",
                    "output_index": 0,
                    "item": {
                        "id": item_id,
                        "type": "message",
                        "status": "in_progress",
                        "role": "assistant",
                        "content": [],
                    },
                },
            )

            # 3. response.content_part.added
            yield _sse_event(
                "response.content_part.added",
                {
                    "type": "response.content_part.added",
                    "item_id": item_id,
                    "content_index": 0,
                    "part": {"type": "output_text", "text": "", "annotations": []},
                },
            )

            # Process the message through our harness
            result = await agent_harness.process_message(db, chat_request)
            assistant_content = result.choices[0].message.content if result.choices else ""

            # 4. Stream text in chunks (simulate streaming by splitting on words)
            words = assistant_content.split(" ")
            chunk_size = 3  # words per delta
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i : i + chunk_size])
                if i + chunk_size < len(words):
                    chunk += " "
                yield _sse_event(
                    "response.output_text.delta",
                    {
                        "type": "response.output_text.delta",
                        "item_id": item_id,
                        "content_index": 0,
                        "delta": chunk,
                    },
                )

            # 5. response.output_text.done
            yield _sse_event(
                "response.output_text.done",
                {
                    "type": "response.output_text.done",
                    "item_id": item_id,
                    "content_index": 0,
                    "text": assistant_content,
                },
            )

            # 6. response.content_part.done
            yield _sse_event(
                "response.content_part.done",
                {
                    "type": "response.content_part.done",
                    "item_id": item_id,
                    "content_index": 0,
                    "part": {"type": "output_text", "text": assistant_content, "annotations": []},
                },
            )

            # 7. response.output_item.done
            yield _sse_event(
                "response.output_item.done",
                {
                    "type": "response.output_item.done",
                    "output_index": 0,
                    "item": {
                        "id": item_id,
                        "type": "message",
                        "status": "completed",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": assistant_content,
                                "annotations": [],
                            }
                        ],
                    },
                },
            )

            # 8. response.completed
            yield _sse_event(
                "response.completed",
                {
                    "type": "response.completed",
                    "response": {
                        "id": response_id,
                        "object": "response",
                        "created_at": created_at,
                        "status": "completed",
                        "model": result.model,
                        "output": [
                            {
                                "id": item_id,
                                "type": "message",
                                "status": "completed",
                                "role": "assistant",
                                "content": [
                                    {
                                        "type": "output_text",
                                        "text": assistant_content,
                                        "annotations": [],
                                    }
                                ],
                            }
                        ],
                        "usage": {
                            "input_tokens": result.usage.prompt_tokens,
                            "output_tokens": result.usage.completion_tokens,
                            "total_tokens": result.usage.total_tokens,
                        },
                    },
                },
            )

        except Exception as e:
            yield _sse_event(
                "error",
                {
                    "type": "error",
                    "message": str(e),
                },
            )

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
