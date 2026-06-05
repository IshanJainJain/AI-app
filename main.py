import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
load_dotenv()

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from auth import get_current_user
from DATABASE import (
    add_image_context,
    add_message,
    create_thread,
    delete_global_context,
    delete_image_context,
    delete_thread,
    get_global_context,
    get_messages,
    get_or_create_first_thread,
    get_thread,
    init_db,
    list_image_contexts,
    list_threads,
    rename_thread,
    set_global_context,
    title_from_prompt,
)
from knowledge_base_api import init_knowledge_base, router as knowledge_base_router
from rag_config import MAX_CONTEXT_TOKENS, RAG_RETRIEVAL_TIMEOUT_SECONDS
from rag_retrieval import retrieve_context
from templates import render_page
from routers.auth import router as auth_router
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI()
app.include_router(knowledge_base_router)

# ── CORS ──────────────────────────────────────────────────────────────────────
# During development: allow Vite dev server.
# In production: set FRONTEND_URL in your .env to your real domain.

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth_router)

# ── Config ────────────────────────────────────────────────────────────────────

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "devstral")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava:latest")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
KNOWLEDGE_BASE_DIR = Path(__file__).with_name("knowledge_base")

# ── Schemas ───────────────────────────────────────────────────────────────────

class PromptRequest(BaseModel):
    prompt: str = Field(..., min_length=1)


class ThreadCreateRequest(BaseModel):
    title: str = "New conversation"


class ThreadRenameRequest(BaseModel):
    title: str = Field(..., min_length=1)


class GlobalContextRequest(BaseModel):
    context: str = ""


class ImageContextRequest(BaseModel):
    filename: str = "uploaded-image"
    image: str = Field(..., min_length=1)
    prompt: Optional[str] = None


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    init_db()
    init_knowledge_base()


# ── LLM helpers ───────────────────────────────────────────────────────────────
def build_context_prompt(global_context: str, messages, retrieval_context: str, prompt: str) -> str:
    history_text = format_thread_context(messages)
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
def build_context_prompt_Ishan(global_context: str, image_contexts, messages, prompt: str) -> str:
    sections = []
    if global_context.strip():
        sections.append(
            "Global context shared across all conversations:\n"
            f"{global_context.strip()}"
        )

    if image_contexts:
        image_context_text = "\n\n".join(
            f"Image: {item['filename']}\n{item['description']}"
            for item in image_contexts
        )
        sections.append(
            "Image context for this conversation:\n"
            f"{image_context_text}"
        )

    history = []
    for message in messages:
        speaker = "User" if message["role"] == "user" else "Assistant"
        history.append(f"{speaker}: {message['content']}")

    history_text = "\n\n".join(history)
    if history_text:
        sections.append(
            "Current conversation history:\n"
            f"{history_text}"
        )

    if not sections:
        return prompt

    context_text = "\n\n".join(sections)
    return (
        "Use the context below when answering. Global context applies to every conversation; "
        "image context applies only to this conversation.\n\n"
        f"{context_text}\n\n"
        f"User: {prompt}\n\nAssistant:"
    )

def format_thread_context(messages, latest_prompt: str | None = None) -> str:
    history_lines = []
    for message in messages:
        speaker = "User" if message["role"] == "user" else "Assistant"
        history_lines.append(f"{speaker}: {message['content']}")

    if latest_prompt is not None:
        history_lines.append(f"User: {latest_prompt}")

    history_text = "\n".join(history_lines).strip() or "No prior messages in this thread."
    return history_text


async def ask_llm(messages, prompt: str) -> dict:
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
        answer = f"Failed to contact LLM backend: {exc}"
        return {
            "answer": answer,
            "thread_context": format_thread_context(messages, prompt),
            "rag_context": retrieval_context,
        }

    data = response.json()
    logger.info("Prompt completed in %.2fs.", time.monotonic() - started_at)
    return {
        "answer": data.get("response", "").strip() or "The model returned an empty response.",
        "thread_context": format_thread_context(messages, prompt),
        "rag_context": retrieval_context,
    }

async def ask_llm_Ishan(thread_id: int, user_id: int, messages, prompt: str) -> str:
    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": build_context_prompt(
            get_global_context(user_id),
            list_image_contexts(thread_id),
            messages,
            prompt,
        ),
        "stream": False,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(OLLAMA_URL, json=payload, timeout=LLM_TIMEOUT_SECONDS)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return f"Failed to contact LLM backend: {exc}"

    data = response.json()
    return data.get("response", "").strip() or "The model returned an empty response."


async def describe_image(image_base64: str, prompt: Optional[str]) -> str:
    payload = {
        "model":  OLLAMA_VISION_MODEL,
        "prompt": prompt or (
            "Extract all readable text from this image. Also describe the important visual "
            "details that should be remembered as context for future conversations."
        ),
        "images": [image_base64],
        "stream": False,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(OLLAMA_URL, json=payload, timeout=LLM_TIMEOUT_SECONDS)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to contact image LLM backend: {exc}")

    data = response.json()
    description = data.get("response", "").strip()
    if not description:
        raise HTTPException(status_code=502, detail="Image LLM returned an empty response")
    return description





# ── Thread helper ─────────────────────────────────────────────────────────────

def thread_payload(thread_id: int, user_id: int):
    thread = get_thread(thread_id, user_id)

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    return {
        "thread":        thread,
        "threads":       list_threads(user_id),
        "messages":      get_messages(thread_id),
        "globalContext": get_global_context(user_id),
        "imageContexts": list_image_contexts(thread_id),
    }


# ── Users/me ──────────────────────────────────────────────────────────────────

@app.get("/users/me")
def api_get_me(current_user=Depends(get_current_user)):
    return {
        "id":         current_user["id"],
        "email":      current_user["email"],
        "username":   current_user["username"],
        "created_at": current_user["created_at"],
    }


# ── UI (placeholder until React build is served) ──────────────────────────────

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

# ── Global context ────────────────────────────────────────────────────────────

@app.get("/api/global-context")
def api_get_global_context(current_user=Depends(get_current_user)):
    return {"context": get_global_context(current_user["id"])}


@app.put("/api/global-context")
def api_set_global_context(request: GlobalContextRequest, current_user=Depends(get_current_user)):
    set_global_context(current_user["id"], request.context)
    return {"context": get_global_context(current_user["id"])}


@app.delete("/api/global-context")
def api_delete_global_context(current_user=Depends(get_current_user)):
    delete_global_context(current_user["id"])
    return {"context": get_global_context(current_user["id"])}


# ── Image contexts ────────────────────────────────────────────────────────────

@app.get("/api/threads/{thread_id}/image-contexts")
def api_list_image_contexts(thread_id: int, current_user=Depends(get_current_user)):
    if not get_thread(thread_id, current_user["id"]):
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"imageContexts": list_image_contexts(thread_id)}


@app.post("/api/threads/{thread_id}/image-contexts")
async def api_create_image_context(
    thread_id: int,
    request: ImageContextRequest,
    current_user=Depends(get_current_user),
):
    if not get_thread(thread_id, current_user["id"]):
        raise HTTPException(status_code=404, detail="Thread not found")

    image_base64 = request.image.split(",", 1)[-1]
    description = await describe_image(image_base64, request.prompt)
    image_context_id = add_image_context(thread_id, request.filename, description, OLLAMA_VISION_MODEL)
    return {
        "imageContext": {
            "id":          image_context_id,
            "thread_id":   thread_id,
            "filename":    request.filename,
            "description": description,
            "model":       OLLAMA_VISION_MODEL,
        },
        "imageContexts": list_image_contexts(thread_id),
    }


@app.delete("/api/threads/{thread_id}/image-contexts/{image_context_id}")
def api_delete_image_context(
    thread_id: int,
    image_context_id: int,
    current_user=Depends(get_current_user),
):
    if not get_thread(thread_id, current_user["id"]):
        raise HTTPException(status_code=404, detail="Thread not found")
    if not delete_image_context(thread_id, image_context_id):
        raise HTTPException(status_code=404, detail="Image context not found")
    return {"imageContexts": list_image_contexts(thread_id)}


# ── Threads ───────────────────────────────────────────────────────────────────

@app.get("/api/threads")
def api_list_threads(current_user=Depends(get_current_user)):
    return {"threads": list_threads(current_user["id"])}


@app.post("/api/threads")
def api_create_thread(request: ThreadCreateRequest, current_user=Depends(get_current_user)):
    thread_id = create_thread(user_id=current_user["id"], title=request.title)
    return thread_payload(thread_id, current_user["id"])


@app.get("/api/threads/{thread_id}")
def api_get_thread(thread_id: int, current_user=Depends(get_current_user)):
    return thread_payload(thread_id, current_user["id"])


@app.patch("/api/threads/{thread_id}")
def api_rename_thread(
    thread_id: int,
    request: ThreadRenameRequest,
    current_user=Depends(get_current_user),
):
    if not get_thread(thread_id, current_user["id"]):
        raise HTTPException(status_code=404, detail="Thread not found")
    rename_thread(thread_id, current_user["id"], request.title)
    return thread_payload(thread_id, current_user["id"])


@app.delete("/api/threads/{thread_id}")
def api_delete_thread(thread_id: int, current_user=Depends(get_current_user)):
    if not delete_thread(thread_id, current_user["id"]):
        raise HTTPException(status_code=404, detail="Thread not found")

    active_thread_id = get_or_create_first_thread(current_user["id"])
    return thread_payload(active_thread_id, current_user["id"])


@app.post("/api/threads/{thread_id}/prompt")
async def handle_prompt(
    thread_id: int,
    request: PromptRequest,
    current_user=Depends(get_current_user),
):
    if not get_thread(thread_id, current_user["id"]):
        raise HTTPException(status_code=404, detail="Thread not found")

    prompt = request.prompt.strip()
    previous_messages = get_messages(thread_id)
    ai_response = await ask_llm(thread_id, current_user["id"], previous_messages, prompt)

    add_message(thread_id, "user", prompt)
    add_message(
        thread_id,
        "assistant",
        ai_response["answer"],
        thread_context=ai_response["thread_context"],
        rag_context=ai_response["rag_context"],
    )

    if not previous_messages:
        rename_thread(thread_id, current_user["id"], title_from_prompt(prompt))

    return thread_payload(thread_id, current_user["id"])
