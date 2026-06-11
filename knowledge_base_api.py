import asyncio
import re
import os
import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ingestion_jobs import jobs
from rag_ingestion import (
    SUPPORTED_DOCUMENT_EXTENSIONS,
    chunks_for_document,
    ingest_document_with_progress,
    supported_document_types,
)
from rag_reindex import rebuild_knowledge_base_indexes
from rag_store import remove_document_chunks

router = APIRouter(prefix="/api/knowledge-base", tags=["knowledge-base"])

KNOWLEDGE_BASE_DIR = Path(__file__).with_name("knowledge_base")
SAFE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,79}$")
MAX_DOCUMENT_BYTES = int(os.getenv("MAX_DOCUMENT_BYTES", str(50 * 1024 * 1024)))


class KnowledgeFolderRequest(BaseModel):
    parent: str = ""
    name: str = Field(..., min_length=1)


def init_knowledge_base():
    KNOWLEDGE_BASE_DIR.mkdir(exist_ok=True)


def validate_entry_name(name: str) -> str:
    clean_name = name.strip()
    if (
        not SAFE_NAME_PATTERN.fullmatch(clean_name)
        or clean_name in {".", ".."}
        or "/" in clean_name
        or "\\" in clean_name
    ):
        raise HTTPException(
            status_code=400,
            detail="Use letters, numbers, spaces, dots, underscores, or hyphens only.",
        )
    return clean_name


def knowledge_path(relative_path: str = "") -> Path:
    init_knowledge_base()
    candidate = (KNOWLEDGE_BASE_DIR / relative_path.strip("/")).resolve()
    root = KNOWLEDGE_BASE_DIR.resolve()
    if candidate != root and root not in candidate.parents:
        raise HTTPException(status_code=400, detail="Invalid knowledge base path")
    return candidate


def relative_knowledge_path(path: Path) -> str:
    return path.resolve().relative_to(KNOWLEDGE_BASE_DIR.resolve()).as_posix()


def ingestion_status_for_path(relative_path: str) -> dict | None:
    job = jobs.get_by_source(relative_path)
    if not job or job.phase in {"complete", "failed"}:
        return None
    return jobs.to_dict(job)


def knowledge_payload(relative_path: str = ""):
    current_path = knowledge_path(relative_path)
    if not current_path.exists() or not current_path.is_dir():
        raise HTTPException(status_code=404, detail="Folder not found")

    folders = []
    files = []
    for item in sorted(current_path.iterdir(), key=lambda entry: (entry.is_file(), entry.name.lower())):
        if item.name.startswith("."):
            continue
        if item.is_dir():
            folders.append({
                "name": item.name,
                "path": relative_knowledge_path(item),
            })
        elif item.is_file():
            file_path = relative_knowledge_path(item)
            file_entry = {
                "name": item.name,
                "path": file_path,
                "size": item.stat().st_size,
            }
            ingestion = ingestion_status_for_path(file_path)
            if ingestion:
                file_entry["ingestion"] = ingestion
            files.append(file_entry)

    root = KNOWLEDGE_BASE_DIR.resolve()
    relative = "" if current_path == root else relative_knowledge_path(current_path)
    parent = ""
    if relative:
        parent_path = current_path.parent
        parent = "" if parent_path == root else relative_knowledge_path(parent_path)

    return {
        "path": relative,
        "parent": parent,
        "folders": folders,
        "files": files,
        "active_ingestions": [jobs.to_dict(job) for job in jobs.list_active()],
    }


async def run_ingestion_job(job_id: str, target: Path, content: bytes):
    relative_path = relative_knowledge_path(target)

    async def on_progress(update: dict):
        jobs.update(job_id, **update)

    try:
        result = await ingest_document_with_progress(
            KNOWLEDGE_BASE_DIR,
            target,
            relative_path,
            content,
            on_progress=on_progress,
        )
        jobs.complete(job_id, result)
    except Exception as exc:
        await remove_document_chunks(KNOWLEDGE_BASE_DIR, relative_path)
        target.unlink(missing_ok=True)
        jobs.fail(job_id, str(exc))


@router.get("")
async def api_get_knowledge_base(path: str = ""):
    return knowledge_payload(path)


@router.get("/ingestion")
async def api_list_ingestion_jobs():
    return {"jobs": [jobs.to_dict(job) for job in jobs.list_active()]}


@router.get("/ingestion/{job_id}")
async def api_get_ingestion_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    return jobs.to_dict(job)


@router.get("/files/chunks")
async def api_get_document_chunks(path: str):
    document_path = knowledge_path(path)
    if not document_path.exists() or not document_path.is_file():
        raise HTTPException(status_code=404, detail="Document not found")
    if Path(document_path.name).suffix.lower() not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise HTTPException(status_code=400, detail="That file type is not indexed")
    return chunks_for_document(KNOWLEDGE_BASE_DIR, relative_knowledge_path(document_path))


@router.post("/folders")
async def api_create_knowledge_folder(request: KnowledgeFolderRequest):
    parent_path = knowledge_path(request.parent)
    if not parent_path.exists() or not parent_path.is_dir():
        raise HTTPException(status_code=404, detail="Parent folder not found")

    folder_path = parent_path / validate_entry_name(request.name)
    if folder_path.exists():
        raise HTTPException(status_code=409, detail="A folder or file already exists with that name")

    folder_path.mkdir()
    return knowledge_payload(request.parent)


@router.post("/files")
async def api_upload_knowledge_file(parent: str = Form(""), file: UploadFile = File(...)):
    parent_path = knowledge_path(parent)
    if not parent_path.exists() or not parent_path.is_dir():
        raise HTTPException(status_code=404, detail="Parent folder not found")

    filename = validate_entry_name(file.filename or "")
    if Path(filename).suffix.lower() not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Supported document types: {supported_document_types()}",
        )

    content = await file.read()
    if len(content) > MAX_DOCUMENT_BYTES:
        raise HTTPException(status_code=400, detail="Document is larger than the configured limit")

    target = parent_path / filename
    if target.exists():
        raise HTTPException(status_code=409, detail="A folder or file already exists with that name")

    target.write_bytes(content)
    relative_path = relative_knowledge_path(target)
    job = jobs.create(relative_path)
    jobs.update(
        job.job_id,
        phase="queued",
        progress=0.0,
        chunking_progress=0.0,
        message="File saved. Starting indexing...",
    )
    asyncio.create_task(run_ingestion_job(job.job_id, target, content))

    payload = knowledge_payload(parent)
    payload["job"] = jobs.to_dict(job)
    return payload


@router.delete("/files")
async def api_delete_knowledge_file(path: str):
    target = knowledge_path(path)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Document not found")

    target.unlink()
    await rebuild_knowledge_base_indexes(KNOWLEDGE_BASE_DIR)
    return knowledge_payload(str(target.parent.relative_to(KNOWLEDGE_BASE_DIR)) if target.parent != KNOWLEDGE_BASE_DIR else "")


@router.delete("/folders")
async def api_delete_knowledge_folder(path: str):
    target = knowledge_path(path)
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail="Folder not found")

    shutil.rmtree(target)
    await rebuild_knowledge_base_indexes(KNOWLEDGE_BASE_DIR)
    parent = target.parent
    return knowledge_payload(str(parent.relative_to(KNOWLEDGE_BASE_DIR)) if parent != KNOWLEDGE_BASE_DIR else "")
