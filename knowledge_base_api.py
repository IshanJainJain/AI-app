import re
import os
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from rag_ingestion import (
    SUPPORTED_DOCUMENT_EXTENSIONS,
    ingest_document,
    supported_document_types,
)

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
            files.append({
                "name": item.name,
                "path": relative_knowledge_path(item),
                "size": item.stat().st_size,
            })

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
    }


@router.get("")
async def api_get_knowledge_base(path: str = ""):
    return knowledge_payload(path)


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
    try:
        ingestion = await ingest_document(
            KNOWLEDGE_BASE_DIR,
            target,
            relative_knowledge_path(target),
            content,
        )
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Document ingestion failed: {exc}") from exc

    payload = knowledge_payload(parent)
    payload["ingestion"] = ingestion
    return payload
