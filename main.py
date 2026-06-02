import asyncio
import logging
import os
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from DATABASE import (
    add_message,
    create_thread,
    get_global_context,
    get_messages,
    get_or_create_first_thread,
    get_thread,
    init_db,
    list_threads,
    rename_thread,
    set_global_context,
    title_from_prompt,
)
from knowledge_base_api import init_knowledge_base, router as knowledge_base_router
from rag_config import MAX_CONTEXT_TOKENS, RAG_RETRIEVAL_TIMEOUT_SECONDS
from rag_retrieval import retrieve_context
from templates import render_page

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI()
app.include_router(knowledge_base_router)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "devstral")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
KNOWLEDGE_BASE_DIR = Path(__file__).with_name("knowledge_base")


class PromptRequest(BaseModel):
    prompt: str = Field(..., min_length=1)


class ThreadCreateRequest(BaseModel):
    title: str = "New conversation"


class ThreadRenameRequest(BaseModel):
    title: str = Field(..., min_length=1)


class GlobalContextRequest(BaseModel):
    context: str = ""


@app.on_event("startup")
def startup():
    init_db()
    init_knowledge_base()


def build_context_prompt(global_context: str, messages, retrieval_context: str, prompt: str) -> str:
    history_lines = []
    for message in messages:
        speaker = "User" if message["role"] == "user" else "Assistant"
        history_lines.append(f"{speaker}: {message['content']}")

    history_text = "\n".join(history_lines).strip() or "No prior messages in this thread."
    global_text = global_context.strip() or "No shared global context has been set."
    retrieval_text = retrieval_context.strip() or "No relevant knowledge base chunks were retrieved."

    return (
        "You are a careful assistant inside a persistent chat application.\n"
        "Use the sources below in this order of priority:\n"
        "1. The user's latest question.\n"
        "2. Relevant knowledge base chunks.\n"
        "3. The current thread history.\n"
        "4. Shared global context.\n"
        "Do not invent facts. If the knowledge base conflicts with chat history, explain the conflict briefly and answer conservatively.\n"
        "When using the knowledge base, prefer exact wording from the retrieved chunks for policy, process, or company-specific facts.\n"
        "Keep the answer concise, direct, and useful.\n\n"
        "GLOBAL CONTEXT\n"
        f"{global_text}\n\n"
        "THREAD HISTORY\n"
        f"{history_text}\n\n"
        "RETRIEVED KNOWLEDGE BASE CONTEXT\n"
        f"{retrieval_text}\n\n"
        "USER QUESTION\n"
        f"{prompt}\n\n"
        "ANSWER\n"
    )


async def ask_llm(messages, prompt: str) -> str:
    started_at = time.monotonic()
    try:
        retrieval_context = await asyncio.wait_for(
            retrieve_context(prompt, KNOWLEDGE_BASE_DIR, MAX_CONTEXT_TOKENS),
            timeout=RAG_RETRIEVAL_TIMEOUT_SECONDS,
        )
        logger.info(
            "Retrieved knowledge context in %.2fs (%s chars).",
            time.monotonic() - started_at,
            len(retrieval_context),
        )
    except asyncio.TimeoutError:
        logger.warning("Knowledge retrieval timed out after %.2fs.", RAG_RETRIEVAL_TIMEOUT_SECONDS)
        retrieval_context = ""
    except Exception as exc:
        logger.warning("Knowledge retrieval failed: %s", exc)
        retrieval_context = ""

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": build_context_prompt(
            get_global_context(),
            messages,
            retrieval_context,
            prompt,
        ),
        "stream": False,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(OLLAMA_URL, json=payload, timeout=LLM_TIMEOUT_SECONDS)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("LLM request failed after %.2fs: %s", time.monotonic() - started_at, exc)
        return f"Failed to contact LLM backend: {exc}"

    data = response.json()
    logger.info("Prompt completed in %.2fs.", time.monotonic() - started_at)
    return data.get("response", "").strip() or "The model returned an empty response."


def thread_payload(thread_id: int):
    thread = get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    return {
        "thread": thread,
        "threads": list_threads(),
        "messages": get_messages(thread_id),
        "globalContext": get_global_context(),
    }


@app.get("/", response_class=HTMLResponse)
async def get_ui():
    active_thread_id = get_or_create_first_thread()
    return render_page(
        threads=list_threads(),
        messages=get_messages(active_thread_id),
        active_thread_id=active_thread_id,
        global_context=get_global_context(),
        model=OLLAMA_MODEL,
    )


@app.get("/api/global-context")
async def api_get_global_context():
    return {"context": get_global_context()}


@app.put("/api/global-context")
async def api_set_global_context(request: GlobalContextRequest):
    set_global_context(request.context)
    return {"context": get_global_context()}


@app.get("/api/threads")
async def api_list_threads():
    return {"threads": list_threads()}


@app.post("/api/threads")
async def api_create_thread(request: ThreadCreateRequest):
    thread_id = create_thread(request.title)
    return thread_payload(thread_id)


@app.get("/api/threads/{thread_id}")
async def api_get_thread(thread_id: int):
    return thread_payload(thread_id)


@app.patch("/api/threads/{thread_id}")
async def api_rename_thread(thread_id: int, request: ThreadRenameRequest):
    if not get_thread(thread_id):
        raise HTTPException(status_code=404, detail="Thread not found")
    rename_thread(thread_id, request.title)
    return thread_payload(thread_id)


@app.post("/api/threads/{thread_id}/prompt")
async def handle_prompt(thread_id: int, request: PromptRequest):
    if not get_thread(thread_id):
        raise HTTPException(status_code=404, detail="Thread not found")

    prompt = request.prompt.strip()
    previous_messages = get_messages(thread_id)
    ai_response = await ask_llm(previous_messages, prompt)

    add_message(thread_id, "user", prompt)
    add_message(thread_id, "assistant", ai_response)

    if not previous_messages:
        rename_thread(thread_id, title_from_prompt(prompt))

    return thread_payload(thread_id)
