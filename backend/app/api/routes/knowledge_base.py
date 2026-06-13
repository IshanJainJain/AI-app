"""Knowledge base CRUD — folder management, file upload, chunk inspection."""
import re
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.config import settings
from app.rag.ingestion import SUPPORTED_DOCUMENT_EXTENSIONS, chunks_for_document, supported_document_types

router = APIRouter()

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,79}$")


def _kb_dir() -> Path:
    p = Path(settings.KNOWLEDGE_BASE_DIR)
    p.mkdir(exist_ok=True)
    return p


def _validate_name(name: str) -> str:
    clean = name.strip()
    if not _SAFE_NAME.fullmatch(clean) or clean in {".", ".."} or "/" in clean or "\\" in clean:
        raise HTTPException(400, "Use letters, numbers, spaces, dots, underscores, or hyphens only.")
    return clean


def _kb_path(relative: str = "") -> Path:
    kb = _kb_dir()
    candidate = (kb / relative.strip("/")).resolve()
    root = kb.resolve()
    if candidate != root and root not in candidate.parents:
        raise HTTPException(400, "Invalid knowledge base path")
    return candidate


def _rel(path: Path) -> str:
    return path.resolve().relative_to(_kb_dir().resolve()).as_posix()


def _payload(relative: str = "") -> dict:
    current = _kb_path(relative)
    if not current.exists() or not current.is_dir():
        raise HTTPException(404, "Folder not found")

    folders, files = [], []
    for item in sorted(current.iterdir(), key=lambda e: (e.is_file(), e.name.lower())):
        if item.name.startswith("."):
            continue
        if item.is_dir():
            folders.append({"name": item.name, "path": _rel(item)})
        elif item.is_file():
            files.append({"name": item.name, "path": _rel(item), "size": item.stat().st_size})

    root = _kb_dir().resolve()
    rel = "" if current.resolve() == root else _rel(current)
    parent = ""
    if rel:
        pp = current.parent
        parent = "" if pp.resolve() == root else _rel(pp)

    return {"path": rel, "parent": parent, "folders": folders, "files": files}


class FolderRequest(BaseModel):
    parent: str = ""
    name: str = Field(..., min_length=1)


@router.get("")
async def get_kb(path: str = ""):
    return _payload(path)


@router.get("/files/chunks")
async def get_chunks(path: str):
    doc_path = _kb_path(path)
    if not doc_path.exists() or not doc_path.is_file():
        raise HTTPException(404, "Document not found")
    if Path(doc_path.name).suffix.lower() not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise HTTPException(400, "That file type is not indexed")
    return chunks_for_document(_kb_dir(), _rel(doc_path))


@router.post("/folders")
async def create_folder(request: FolderRequest):
    parent = _kb_path(request.parent)
    if not parent.exists() or not parent.is_dir():
        raise HTTPException(404, "Parent folder not found")
    folder = parent / _validate_name(request.name)
    if folder.exists():
        raise HTTPException(409, "A folder or file already exists with that name")
    folder.mkdir()
    return _payload(request.parent)


@router.post("/files")
async def upload_file(parent: str = Form(""), file: UploadFile = File(...)):
    parent_path = _kb_path(parent)
    if not parent_path.exists() or not parent_path.is_dir():
        raise HTTPException(404, "Parent folder not found")

    filename = _validate_name(file.filename or "")
    if Path(filename).suffix.lower() not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise HTTPException(400, f"Supported types: {supported_document_types()}")

    content = await file.read()
    if len(content) > settings.MAX_DOCUMENT_BYTES:
        raise HTTPException(400, "Document exceeds the configured size limit")

    target = parent_path / filename
    if target.exists():
        raise HTTPException(409, "A file already exists with that name")

    target.write_bytes(content)
    try:
        from app.rag.ingestion import ingest_document
        ingestion = await ingest_document(_kb_dir(), target, _rel(target), content)
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(400, f"Document ingestion failed: {exc}") from exc

    result = _payload(parent)
    result["ingestion"] = ingestion
    return result
