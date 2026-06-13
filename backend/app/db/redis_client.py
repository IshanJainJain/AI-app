"""Async Redis client — pub/sub and simple caching."""
import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

_redis: Optional[aioredis.Redis] = None
# Dedicated client for PubSub: socket_timeout=None so long-lived listen() calls
# never time out waiting for a message.  redis-py ≥ 8.x changed the default
# socket_timeout from None to 5 s, which caused _forward_redis to error every
# 5 s, closing the WebSocket and inflating the event counter.
_redis_pubsub: Optional[aioredis.Redis] = None


async def connect_redis():
    global _redis, _redis_pubsub
    # max_connections=50: headroom for pubsub subscriptions (each uses 1 dedicated connection)
    _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True, max_connections=50)
    _redis_pubsub = aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        max_connections=10,
        socket_timeout=None,   # no read timeout — pubsub.listen() blocks until a message arrives
    )
    await _redis.ping()
    logger.info("Redis connected")


async def disconnect_redis():
    if _redis:
        await _redis.aclose()
    if _redis_pubsub:
        await _redis_pubsub.aclose()
    logger.info("Redis disconnected")


def get_redis() -> aioredis.Redis:
    if _redis is None:
        raise RuntimeError("Redis not initialised — call connect_redis() first")
    return _redis


def get_redis_pubsub() -> aioredis.Redis:
    if _redis_pubsub is None:
        raise RuntimeError("Redis pubsub not initialised — call connect_redis() first")
    return _redis_pubsub


# ── Cache helpers ─────────────────────────────────────────────────────────────

async def cache_set(key: str, value: Any, ttl: int = 300):
    await get_redis().setex(key, ttl, json.dumps(value))


async def cache_get(key: str) -> Optional[Any]:
    raw = await get_redis().get(key)
    return json.loads(raw) if raw else None


async def cache_delete(key: str):
    await get_redis().delete(key)


async def cache_task_status(task_id: str, status: str, meta: dict = None, ttl: int = 3600):
    await cache_set(f"task:{task_id}", {"status": status, **(meta or {})}, ttl=ttl)


# ── Pub/sub helpers ───────────────────────────────────────────────────────────

async def publish_event(channel: str, payload: dict):
    await get_redis().publish(channel, json.dumps(payload))


async def publish_chat_event(thread_id: str, event: dict):
    """Publish an event on the per-thread channel."""
    await publish_event(f"chat:{thread_id}", event)


async def subscribe_thread(thread_id: str):
    """Return a PubSub handle subscribed to the thread channel.
    Uses the no-timeout pubsub client so listen() never times out between messages.
    """
    pubsub = get_redis_pubsub().pubsub()
    await pubsub.subscribe(f"chat:{thread_id}")
    return pubsub


async def subscribe_global():
    """Return a PubSub handle subscribed to the global events channel.
    Uses the no-timeout pubsub client so listen() never times out between messages.
    """
    pubsub = get_redis_pubsub().pubsub()
    await pubsub.subscribe("events")
    return pubsub


async def publish_hil_decision(request_id: str, payload: dict):
    await publish_event(f"hil:{request_id}", payload)


async def wait_for_hil_decision(request_id: str, timeout_seconds: int = 300) -> Optional[dict]:
    pubsub = get_redis_pubsub().pubsub()
    await pubsub.subscribe(f"hil:{request_id}")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                return json.loads(message["data"])
    finally:
        await pubsub.unsubscribe(f"hil:{request_id}")
        await pubsub.aclose()
    return None
