import os

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
from templates import render_page

app = FastAPI()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))


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


def build_context_prompt(global_context: str, messages, prompt: str) -> str:
    sections = []
    if global_context.strip():
        sections.append(
            "Global context shared across all conversations:\n"
            f"{global_context.strip()}"
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
        "Use the context below when answering. The global context applies to every conversation.\n\n"
        f"{context_text}\n\n"
        f"User: {prompt}\n\nAssistant:"
    )


async def ask_llm(messages, prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": build_context_prompt(get_global_context(), messages, prompt),
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
