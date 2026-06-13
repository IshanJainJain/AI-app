"""
WebSocket endpoints.

/ws/chat/{thread_id}?token=...   — streaming ReAct chat
/ws/events?token=...             — global event feed (Redis pub/sub)
"""
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.routes.auth import decode_access_token
from app.db.mongodb import (
    add_message, get_global_context, get_messages, get_thread,
    get_user_by_id, list_image_contexts, rename_thread, title_from_prompt,
)
from app.db.redis_client import publish_chat_event, subscribe_global, subscribe_thread

logger = logging.getLogger(__name__)
router = APIRouter()


async def _authenticate_ws(websocket: WebSocket, token: str) -> dict | None:
    user_id = decode_access_token(token)
    if not user_id:
        await websocket.close(code=4001, reason="Invalid token")
        return None
    user = await get_user_by_id(user_id)
    if not user:
        await websocket.close(code=4001, reason="User not found")
        return None
    return user


@router.websocket("/chat/{thread_id}")
async def ws_chat(websocket: WebSocket, thread_id: str, token: str = ""):
    await websocket.accept()

    user = await _authenticate_ws(websocket, token)
    if not user:
        return

    thread = await get_thread(thread_id, user["_id"])
    if not thread:
        await websocket.send_json({"type": "error", "content": "Thread not found"})
        await websocket.close(code=4004)
        return

    await websocket.send_json({"type": "connected", "thread_id": thread_id})

    from app.agents.chat_agent import ChatAgent
    agent = ChatAgent()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "content": "Invalid JSON"})
                continue

            if data.get("type") != "message":
                continue

            prompt = (data.get("content") or "").strip()
            if not prompt:
                continue

            previous = await get_messages(thread_id)
            context = {
                "thread_id": thread_id,
                "user_id": user["_id"],
                "prompt": prompt,
                "messages": previous,
                "global_context": await get_global_context(user["_id"]),
                "image_contexts": await list_image_contexts(thread_id),
            }

            # Stream agent events
            thoughts = []
            tool_calls = []
            final_response = ""

            async for event in agent.stream(context):
                await websocket.send_json(event)
                event_type = event.get("type")
                if event_type == "agent_thinking":
                    thoughts.append({"thought": event.get("content", ""), "step": event.get("step")})
                elif event_type == "tool_call":
                    tool_calls.append({"tool": event.get("tool"), "step": event.get("step"), "params": event.get("params")})
                elif event_type == "agent_response":
                    final_response = event.get("content", "")
                    thoughts = event.get("thoughts", thoughts)
                    tool_calls = event.get("tool_calls", tool_calls)

            # Persist messages
            if final_response:
                await add_message(thread_id, "user", prompt)
                msg_id = await add_message(
                    thread_id,
                    "assistant",
                    final_response,
                    agent_thoughts=thoughts,
                    tool_calls=tool_calls,
                )
                if not previous:
                    await rename_thread(thread_id, user["_id"], title_from_prompt(prompt))

                await websocket.send_json({"type": "message_saved", "message_id": msg_id})
                await publish_chat_event(thread_id, {
                    "type": "new_message",
                    "thread_id": thread_id,
                    "role": "assistant",
                })

    except WebSocketDisconnect:
        logger.info("WS chat disconnected: thread=%s user=%s", thread_id, user["_id"])


@router.websocket("/events")
async def ws_events(websocket: WebSocket, token: str = ""):
    await websocket.accept()

    user = await _authenticate_ws(websocket, token)
    if not user:
        return

    await websocket.send_json({"type": "connected"})

    try:
        pubsub = await subscribe_global()
    except Exception as exc:
        logger.error("Could not subscribe to Redis events channel: %s", exc)
        await websocket.close(code=1011)
        return

    # Forward Redis → WebSocket in a background task.
    # Use asyncio.wait so that a WebSocket disconnect (detected via
    # _wait_disconnect) cancels the Redis listener, preventing connection leaks.
    #
    # NOTE: subscribe_global() uses a dedicated Redis client with socket_timeout=None
    # so pubsub.listen() blocks indefinitely waiting for messages without timing out.
    # (redis-py ≥ 8.x defaults socket_timeout to 5 s which would close the WS every 5 s.)
    async def _forward_redis():
        try:
            while True:
                try:
                    async for message in pubsub.listen():
                        if message["type"] == "message":
                            await websocket.send_text(message["data"])
                except asyncio.CancelledError:
                    return  # cancelled when client disconnects — exit cleanly
                except Exception as exc:
                    # Transient error on the pubsub socket — log and retry rather
                    # than letting the WebSocket close (which would inflate the event counter).
                    logger.warning(
                        "ws_events _forward_redis transient error (retrying): %s: %s",
                        type(exc).__name__, exc,
                    )
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    async def _wait_disconnect():
        """Drain any incoming frames; exit on client disconnect."""
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        except Exception:
            pass  # any other error (e.g. disconnect mid-read) — just exit

    forward_task = asyncio.create_task(_forward_redis())
    disconnect_task = asyncio.create_task(_wait_disconnect())

    try:
        await asyncio.wait(
            {forward_task, disconnect_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
    finally:
        for task in (forward_task, disconnect_task):
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
        try:
            await pubsub.unsubscribe("events")
            await pubsub.aclose()
        except Exception:
            pass
