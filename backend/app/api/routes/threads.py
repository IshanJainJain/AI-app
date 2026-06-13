"""Thread and message routes."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.db.mongodb import (
    add_message, create_thread, delete_thread, get_messages,
    get_or_create_first_thread, get_thread, list_threads,
    rename_thread, title_from_prompt, get_global_context, list_image_contexts,
)

router = APIRouter()


class ThreadCreateRequest(BaseModel):
    title: str = "New conversation"


class ThreadRenameRequest(BaseModel):
    title: str = Field(..., min_length=1)


class PromptRequest(BaseModel):
    prompt: str = Field(..., min_length=1)


async def _thread_payload(thread_id: str, user_id: str) -> dict:
    thread = await get_thread(thread_id, user_id)
    if not thread:
        raise HTTPException(404, "Thread not found")
    return {
        "thread": thread,
        "threads": await list_threads(user_id),
        "messages": await get_messages(thread_id),
        "globalContext": await get_global_context(user_id),
        "imageContexts": await list_image_contexts(thread_id),
    }


@router.get("")
async def list_threads_route(current_user=Depends(get_current_user)):
    return {"threads": await list_threads(current_user["_id"])}


@router.post("")
async def create_thread_route(request: ThreadCreateRequest, current_user=Depends(get_current_user)):
    thread_id = await create_thread(user_id=current_user["_id"], title=request.title)
    return await _thread_payload(thread_id, current_user["_id"])


@router.get("/{thread_id}")
async def get_thread_route(thread_id: str, current_user=Depends(get_current_user)):
    return await _thread_payload(thread_id, current_user["_id"])


@router.patch("/{thread_id}")
async def rename_thread_route(
    thread_id: str,
    request: ThreadRenameRequest,
    current_user=Depends(get_current_user),
):
    if not await get_thread(thread_id, current_user["_id"]):
        raise HTTPException(404, "Thread not found")
    await rename_thread(thread_id, current_user["_id"], request.title)
    return await _thread_payload(thread_id, current_user["_id"])


@router.delete("/{thread_id}")
async def delete_thread_route(thread_id: str, current_user=Depends(get_current_user)):
    if not await delete_thread(thread_id, current_user["_id"]):
        raise HTTPException(404, "Thread not found")
    active_id = await get_or_create_first_thread(current_user["_id"])
    return await _thread_payload(active_id, current_user["_id"])


@router.post("/{thread_id}/prompt")
async def handle_prompt(
    thread_id: str,
    request: PromptRequest,
    current_user=Depends(get_current_user),
):
    """
    REST fallback for non-WebSocket clients.
    Runs the ChatAgent synchronously and saves the result.
    """
    from app.agents.chat_agent import ChatAgent
    from app.db.mongodb import get_global_context, list_image_contexts

    if not await get_thread(thread_id, current_user["_id"]):
        raise HTTPException(404, "Thread not found")

    prompt = request.prompt.strip()
    previous = await get_messages(thread_id)

    agent = ChatAgent()
    context = {
        "thread_id": thread_id,
        "user_id": current_user["_id"],
        "prompt": prompt,
        "messages": previous,
        "global_context": await get_global_context(current_user["_id"]),
        "image_contexts": await list_image_contexts(thread_id),
    }

    result = await agent.run(context)
    ai_response = result.get("response", "")

    await add_message(thread_id, "user", prompt)
    await add_message(
        thread_id,
        "assistant",
        ai_response,
        agent_thoughts=result.get("thoughts", []),
        tool_calls=result.get("tool_calls", []),
    )

    if not previous:
        await rename_thread(thread_id, current_user["_id"], title_from_prompt(prompt))

    return await _thread_payload(thread_id, current_user["_id"])
