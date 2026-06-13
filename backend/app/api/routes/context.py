"""Global context and image context routes."""
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.config import settings
from app.db.mongodb import (
    add_image_context, delete_image_context, delete_global_context,
    get_global_context, get_thread, list_image_contexts, set_global_context,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class GlobalContextRequest(BaseModel):
    context: str = ""


class ImageContextRequest(BaseModel):
    filename: str = "uploaded-image"
    image: str = Field(..., min_length=1)
    prompt: Optional[str] = None


# ── Global context ────────────────────────────────────────────────────────────

@router.get("/global-context")
async def get_gc(current_user=Depends(get_current_user)):
    return {"context": await get_global_context(current_user["_id"])}


@router.put("/global-context")
async def set_gc(request: GlobalContextRequest, current_user=Depends(get_current_user)):
    await set_global_context(current_user["_id"], request.context)
    return {"context": await get_global_context(current_user["_id"])}


@router.delete("/global-context")
async def delete_gc(current_user=Depends(get_current_user)):
    await delete_global_context(current_user["_id"])
    return {"context": ""}


# ── Image contexts ────────────────────────────────────────────────────────────

@router.get("/threads/{thread_id}/image-contexts")
async def list_img_ctx(thread_id: str, current_user=Depends(get_current_user)):
    if not await get_thread(thread_id, current_user["_id"]):
        raise HTTPException(404, "Thread not found")
    return {"imageContexts": await list_image_contexts(thread_id)}


@router.post("/threads/{thread_id}/image-contexts")
async def create_img_ctx(
    thread_id: str,
    request: ImageContextRequest,
    current_user=Depends(get_current_user),
):
    if not await get_thread(thread_id, current_user["_id"]):
        raise HTTPException(404, "Thread not found")

    image_b64 = request.image.split(",", 1)[-1]
    description = await _describe_image(image_b64, request.prompt)

    ctx_id = await add_image_context(thread_id, request.filename, description, settings.VISION_LLM_MODEL)
    return {
        "imageContext": {
            "id": ctx_id,
            "thread_id": thread_id,
            "filename": request.filename,
            "description": description,
            "model": settings.VISION_LLM_MODEL,
        },
        "imageContexts": await list_image_contexts(thread_id),
    }


@router.delete("/threads/{thread_id}/image-contexts/{ctx_id}")
async def delete_img_ctx(
    thread_id: str,
    ctx_id: str,
    current_user=Depends(get_current_user),
):
    if not await get_thread(thread_id, current_user["_id"]):
        raise HTTPException(404, "Thread not found")
    if not await delete_image_context(thread_id, ctx_id):
        raise HTTPException(404, "Image context not found")
    return {"imageContexts": await list_image_contexts(thread_id)}


async def _describe_image(image_b64: str, prompt: Optional[str]) -> str:
    payload = {
        "model": settings.VISION_LLM_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt or (
                    "Extract all readable text from this image. "
                    "Also describe the important visual details for future context."
                )},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            ],
        }],
        "max_tokens": 1024,
    }
    try:
        from openai import AsyncOpenAI
        llm = AsyncOpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)
        resp = await llm.chat.completions.create(**payload)
        text = resp.choices[0].message.content or ""
        if not text:
            raise HTTPException(502, "Vision model returned an empty response")
        return text
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"Vision model error: {exc}") from exc
