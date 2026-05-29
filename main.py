import os
from typing import Optional

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
from routers.auth import router as auth_router

app = FastAPI()

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

OLLAMA_URL          = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL        = os.getenv("OLLAMA_MODEL", "ministral")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava:latest")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))


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


# ── LLM helpers ───────────────────────────────────────────────────────────────

def build_context_prompt(global_context: str, image_contexts, messages, prompt: str) -> str:
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


async def ask_llm(thread_id: int, user_id: int, messages, prompt: str) -> str:
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
    return """<!doctype html>
<html><body style="font-family:sans-serif;padding:2rem">
<h1>API is running</h1>
<p>The React frontend is not built yet.
   Run <code>npm run build</code> inside <code>frontend/</code> and mount the dist folder.</p>
</body></html>"""


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
    add_message(thread_id, "assistant", ai_response)

    if not previous_messages:
        rename_thread(thread_id, current_user["id"], title_from_prompt(prompt))

    return thread_payload(thread_id, current_user["id"])
