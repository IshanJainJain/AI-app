"""Async MongoDB client (Motor) with CRUD helpers."""
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from bson import ObjectId

from app.config import settings

logger = logging.getLogger(__name__)

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


async def connect_mongodb():
    global _client, _db
    _client = AsyncIOMotorClient(settings.MONGODB_URL)
    _db = _client[settings.MONGODB_DB]
    # Ensure indexes
    await _db.users.create_index("email", unique=True)
    await _db.users.create_index("username", unique=True)
    await _db.users.create_index("google_id", sparse=True)
    await _db.threads.create_index([("user_id", 1), ("updated_at", -1)])
    await _db.messages.create_index([("thread_id", 1), ("created_at", 1)])
    await _db.image_contexts.create_index("thread_id")
    await _db.settings.create_index("key", unique=True)
    await _db.knowledge_docs.create_index("path", unique=True)
    await _db.agent_tasks.create_index("task_id", unique=True)
    logger.info("MongoDB connected")


async def disconnect_mongodb():
    if _client:
        _client.close()
    logger.info("MongoDB disconnected")


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("MongoDB not initialised — call connect_mongodb() first")
    return _db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize(doc: dict) -> dict:
    """Convert ObjectId → str and add id field."""
    if doc is None:
        return {}
    doc = dict(doc)
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


# ── Generic helpers ───────────────────────────────────────────────────────────

async def find_one(collection: str, query: dict) -> Optional[dict]:
    doc = await get_db()[collection].find_one(query)
    return _serialize(doc) if doc else None


async def find_many(collection: str, query: dict, sort: list = None, limit: int = 0) -> list[dict]:
    cursor = get_db()[collection].find(query)
    if sort:
        cursor = cursor.sort(sort)
    if limit:
        cursor = cursor.limit(limit)
    return [_serialize(d) async for d in cursor]


async def insert_one(collection: str, doc: dict) -> str:
    result = await get_db()[collection].insert_one(doc)
    return str(result.inserted_id)


async def update_doc(collection: str, query: dict, update: dict):
    await get_db()[collection].update_one(query, update)


async def delete_doc(collection: str, query: dict) -> int:
    result = await get_db()[collection].delete_one(query)
    return result.deleted_count


async def save_agent_task(task_dict: dict):
    await get_db().agent_tasks.update_one(
        {"task_id": task_dict["task_id"]},
        {"$set": task_dict},
        upsert=True,
    )


# ── Users ─────────────────────────────────────────────────────────────────────

async def create_user(email: str, username: str, hashed_password: str = None, google_id: str = None) -> str:
    doc = {
        "email": email.strip().lower(),
        "username": username.strip(),
        "hashed_password": hashed_password,
        "google_id": google_id,
        "created_at": _now(),
    }
    return await insert_one("users", doc)


async def get_user_by_email(email: str) -> Optional[dict]:
    return await find_one("users", {"email": email.strip().lower()})


async def get_user_by_id(user_id: str) -> Optional[dict]:
    try:
        return await find_one("users", {"_id": ObjectId(user_id)})
    except Exception:
        return None


async def get_user_by_google_id(google_id: str) -> Optional[dict]:
    return await find_one("users", {"google_id": google_id})


async def get_user_by_username(username: str) -> Optional[dict]:
    return await find_one("users", {"username": username.strip()})


async def link_google_id(user_id: str, google_id: str):
    await update_doc("users", {"_id": ObjectId(user_id)}, {"$set": {"google_id": google_id}})


# ── Global context ────────────────────────────────────────────────────────────

async def get_global_context(user_id: str) -> str:
    doc = await find_one("settings", {"key": f"global_context:{user_id}"})
    return doc.get("value", "") if doc else ""


async def set_global_context(user_id: str, value: str):
    await get_db().settings.update_one(
        {"key": f"global_context:{user_id}"},
        {"$set": {"value": value.strip()}},
        upsert=True,
    )


async def delete_global_context(user_id: str):
    await delete_doc("settings", {"key": f"global_context:{user_id}"})


# ── Threads ───────────────────────────────────────────────────────────────────

async def create_thread(user_id: str, title: str = "New conversation") -> str:
    now = _now()
    doc = {
        "user_id": user_id,
        "title": title.strip() or "New conversation",
        "created_at": now,
        "updated_at": now,
    }
    return await insert_one("threads", doc)


async def list_threads(user_id: str) -> list[dict]:
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$lookup": {
            "from": "messages",
            "let": {"tid": {"$toString": "$_id"}},
            "pipeline": [
                {"$match": {"$expr": {"$eq": ["$thread_id", "$$tid"]}}},
                {"$count": "n"},
            ],
            "as": "msg_count",
        }},
        {"$addFields": {
            "message_count": {"$ifNull": [{"$arrayElemAt": ["$msg_count.n", 0]}, 0]},
            "id": {"$toString": "$_id"},
        }},
        {"$sort": {"updated_at": -1}},
        {"$project": {"msg_count": 0}},
    ]
    return [_serialize(d) async for d in get_db().threads.aggregate(pipeline)]


async def get_thread(thread_id: str, user_id: str) -> Optional[dict]:
    try:
        doc = await find_one("threads", {"_id": ObjectId(thread_id), "user_id": user_id})
        if doc:
            doc["id"] = doc["_id"]
        return doc
    except Exception:
        return None


async def rename_thread(thread_id: str, user_id: str, title: str):
    await update_doc(
        "threads",
        {"_id": ObjectId(thread_id), "user_id": user_id},
        {"$set": {"title": title.strip() or "New conversation", "updated_at": _now()}},
    )


async def delete_thread(thread_id: str, user_id: str) -> bool:
    tid_str = thread_id
    await get_db().messages.delete_many({"thread_id": tid_str})
    await get_db().image_contexts.delete_many({"thread_id": tid_str})
    result = await get_db().threads.delete_one({"_id": ObjectId(thread_id), "user_id": user_id})
    return result.deleted_count > 0


async def get_or_create_first_thread(user_id: str) -> str:
    threads = await list_threads(user_id)
    if threads:
        return threads[0]["id"]
    return await create_thread(user_id)


# ── Messages ──────────────────────────────────────────────────────────────────

async def add_message(
    thread_id: str,
    role: str,
    content: str,
    agent_thoughts: list = None,
    tool_calls: list = None,
) -> str:
    doc = {
        "thread_id": thread_id,
        "role": role,
        "content": content,
        "agent_thoughts": agent_thoughts or [],
        "tool_calls": tool_calls or [],
        "created_at": _now(),
    }
    msg_id = await insert_one("messages", doc)
    await update_doc("threads", {"_id": ObjectId(thread_id)}, {"$set": {"updated_at": _now()}})
    return msg_id


async def get_messages(thread_id: str) -> list[dict]:
    docs = await find_many("messages", {"thread_id": thread_id}, sort=[("created_at", 1)])
    for d in docs:
        d["id"] = d["_id"]
    return docs


# ── Image contexts ────────────────────────────────────────────────────────────

async def add_image_context(thread_id: str, filename: str, description: str, model: str) -> str:
    doc = {
        "thread_id": thread_id,
        "filename": filename.strip() or "uploaded-image",
        "description": description.strip(),
        "model": model,
        "created_at": _now(),
    }
    return await insert_one("image_contexts", doc)


async def list_image_contexts(thread_id: str) -> list[dict]:
    docs = await find_many("image_contexts", {"thread_id": thread_id}, sort=[("created_at", -1)])
    for d in docs:
        d["id"] = d["_id"]
    return docs


async def delete_image_context(thread_id: str, image_context_id: str) -> bool:
    try:
        result = await get_db().image_contexts.delete_one(
            {"_id": ObjectId(image_context_id), "thread_id": thread_id}
        )
        return result.deleted_count > 0
    except Exception:
        return False


# ── Knowledge base doc metadata ───────────────────────────────────────────────

async def upsert_kb_doc(path: str, metadata: dict):
    await get_db().knowledge_docs.update_one(
        {"path": path},
        {"$set": {**metadata, "path": path, "updated_at": _now()}},
        upsert=True,
    )


async def get_kb_doc(path: str) -> Optional[dict]:
    return await find_one("knowledge_docs", {"path": path})


# ── Helpers ───────────────────────────────────────────────────────────────────

def title_from_prompt(prompt: str) -> str:
    words = prompt.strip().split()
    title = " ".join(words[:8])
    if len(title) > 60:
        title = title[:57].rstrip() + "..."
    return title or "New conversation"
