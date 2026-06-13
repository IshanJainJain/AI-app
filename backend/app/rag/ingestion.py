"""
RAG ingestion pipeline.

Parse → recursive chunk → agentic refinement (OpenAI-compatible LLM) →
embed (Ollama) → FAISS storage.

All config comes from app.config.settings.
"""
import hashlib
import json
import logging
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

SUPPORTED_DOCUMENT_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}
_INTERACTION_LOG = "agentic_chunk_interactions.jsonl"


def supported_document_types() -> str:
    return ", ".join(sorted(SUPPORTED_DOCUMENT_EXTENSIONS))


# ── Document parsing ──────────────────────────────────────────────────────────

def parse_document(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md"}:
        return content.decode("utf-8", errors="replace")
    if suffix == ".pdf":
        return _parse_pdf(content)
    if suffix == ".docx":
        return _parse_docx(content)
    raise ValueError(f"Unsupported document type. Supported: {supported_document_types()}")


def _parse_pdf(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Install pypdf to ingest PDF documents.") from exc
    reader = PdfReader(BytesIO(content))
    return "\n\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()


def _parse_docx(content: bytes) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("Install python-docx to ingest DOCX documents.") from exc
    doc = Document(BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs).strip()


# ── Chunking ──────────────────────────────────────────────────────────────────

def _normalize_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def _fallback_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []

    def recursive_split(t: str, seps: list[str]) -> list[str]:
        if len(t) <= chunk_size:
            return [t.strip()]
        sep = seps[0]
        rest = seps[1:]
        if sep == "":
            return [t[i:i + chunk_size].strip() for i in range(0, len(t), chunk_size)]
        pieces = t.split(sep)
        if len(pieces) == 1:
            return recursive_split(t, rest)
        chunks, current = [], ""
        for piece in pieces:
            piece = piece.strip()
            if not piece:
                continue
            candidate = piece if not current else f"{current}{sep}{piece}"
            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current:
                    chunks.extend(recursive_split(current, rest))
                current = piece
        if current:
            chunks.extend(recursive_split(current, rest))
        return chunks

    raw = recursive_split(normalized, ["\n\n", "\n", ". ", " ", ""])
    merged, current = [], ""
    for chunk in raw:
        if not chunk:
            continue
        if not current:
            current = chunk
            continue
        candidate = f"{current}\n{chunk}"
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            merged.append(current.strip())
            current = (f"{current[-overlap:]}\n{chunk}".strip() if overlap > 0 else chunk)
    if current:
        merged.append(current.strip())
    return [c for c in merged if c]


def _normalize_agentic_chunks(chunks: list[str]) -> list[str]:
    out = []
    max_chars = settings.AGENTIC_CHUNK_MAX_CHARS
    for chunk in chunks:
        if len(chunk) <= max_chars:
            out.append(chunk)
        else:
            out.extend(_fallback_split(chunk, max_chars, 0))
    return out


def _build_prompt(carryover: list[str], window: list[str]) -> str:
    def numbered(items, prefix):
        return "\n\n".join(f"[{prefix}{i+1}]\n{c}" for i, c in enumerate(items))

    return (
        f"You are refining knowledge-base chunks for retrieval.\n\n"
        f"CARRYOVER chunks:\n{numbered(carryover, 'C') or '(none)'}\n\n"
        f"NEW chunks:\n{numbered(window, 'N')}\n\n"
        f"Rules:\n"
        f"- Preserve original wording exactly.\n"
        f"- Keep related clauses together.\n"
        f"- Target chunk size: {settings.AGENTIC_CHUNK_TARGET_CHARS} chars.\n"
        f"- Hard max: {settings.AGENTIC_CHUNK_MAX_CHARS} chars.\n"
        f"- Put trailing uncertain text in 'carryover'.\n"
        f"- Return ONLY valid JSON: "
        f'{{ "final_chunks": ["..."], "carryover": ["..."] }}'
    )


def _parse_llm_response(text: str) -> Optional[dict]:
    text = text.strip().strip("`")
    if text.startswith("json"):
        text = text[4:].strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        payload = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    fc = payload.get("final_chunks", [])
    co = payload.get("carryover", [])
    if not isinstance(fc, list) or not isinstance(co, list):
        return None
    clean = lambda lst: [c.strip() for c in lst if isinstance(c, str) and c.strip()]
    return {"final_chunks": clean(fc), "carryover": clean(co)}


async def _agentic_refine_window(
    client: httpx.AsyncClient,
    carryover: list[str],
    window: list[str],
    log_path: Path,
    source: str,
) -> Optional[dict]:
    prompt = _build_prompt(carryover, window)
    response_text = ""
    result = None
    error = None
    try:
        from openai import AsyncOpenAI
        llm = AsyncOpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)
        resp = await llm.chat.completions.create(
            model=settings.AGENTIC_CHUNK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=4096,
            timeout=settings.AGENTIC_CHUNK_TIMEOUT_SECONDS,
        )
        response_text = resp.choices[0].message.content or ""
        result = _parse_llm_response(response_text)
        return result
    except Exception as exc:
        error = str(exc)
        logger.warning("Agentic chunking failed for %s: %s", source, exc)
        return None
    finally:
        _append_log(log_path, {
            "source": source,
            "carryover_chunks": carryover,
            "window_chunks": window,
            "reply": response_text,
            "parsed": result,
            "error": error,
        })


def _append_log(path: Path, record: dict):
    record["timestamp"] = datetime.now(timezone.utc).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


async def split_text(text: str, knowledge_base_dir: Path, relative_path: str) -> list[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []

    chunk_size = settings.RAG_CHUNK_SIZE
    overlap = settings.RAG_CHUNK_OVERLAP
    base_chunks = _fallback_split(normalized, chunk_size, overlap)
    if not base_chunks:
        return []

    log_path = knowledge_base_dir / settings.VECTOR_STORE_NAME / _INTERACTION_LOG
    window_size = settings.AGENTIC_CHUNK_WINDOW_SIZE
    refined, carryover = [], []

    async with httpx.AsyncClient(timeout=settings.AGENTIC_CHUNK_TIMEOUT_SECONDS) as client:
        start, first = 0, True
        while start < len(base_chunks):
            win = base_chunks[start:start + (window_size if first else max(1, window_size - 1))]
            result = await _agentic_refine_window(client, carryover, win, log_path, relative_path)
            if result is None:
                refined.extend(carryover + win)
                carryover = []
            else:
                refined.extend(result["final_chunks"])
                carryover = result["carryover"]
                if len(carryover) > 1:
                    carryover = ["\n\n".join(carryover).strip()]
            first = False
            start += len(win)

    refined.extend(carryover)
    return _normalize_agentic_chunks([c for c in refined if c])


# ── Embedding ─────────────────────────────────────────────────────────────────

async def embed_chunks(chunks: list[str]) -> list[list[float]]:
    """Embed a list of text chunks via OpenAI-compatible /v1/embeddings endpoint."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.EMBED_API_KEY, base_url=settings.EMBED_BASE_URL)
    vectors = []
    for chunk in chunks:
        response = await client.embeddings.create(
            model=settings.EMBED_MODEL,
            input=chunk,
        )
        embedding = response.data[0].embedding
        if not embedding:
            raise RuntimeError("Embedding model returned an empty vector.")
        vectors.append(embedding)
    return vectors


# ── FAISS storage ─────────────────────────────────────────────────────────────

def store_vectors(
    knowledge_base_dir: Path,
    relative_path: str,
    chunks: list[str],
    vectors: list[list[float]],
    content: bytes,
):
    try:
        import faiss
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("Install faiss-cpu and numpy to store document vectors.") from exc

    vector_dir = knowledge_base_dir / settings.VECTOR_STORE_NAME
    vector_dir.mkdir(exist_ok=True)
    index_path = vector_dir / "faiss.index"
    chunks_path = vector_dir / "chunks.json"

    matrix = np.array(vectors, dtype="float32")
    faiss.normalize_L2(matrix)

    if index_path.exists():
        index = faiss.read_index(str(index_path))
        if index.d != matrix.shape[1]:
            raise RuntimeError("FAISS index dimension mismatch — rebuild vector store after changing embedding model.")
    else:
        index = faiss.IndexFlatIP(matrix.shape[1])

    existing = json.loads(chunks_path.read_text(encoding="utf-8")) if chunks_path.exists() else []
    doc_hash = hashlib.sha256(content).hexdigest()
    start_idx = len(existing)

    records = [
        {
            "id": start_idx + i,
            "text": chunk,
            "metadata": {
                "source": relative_path,
                "chunk": i,
                "sha256": doc_hash,
                "embedding_model": settings.EMBED_MODEL,
                "chunking_model": settings.AGENTIC_CHUNK_MODEL,
            },
        }
        for i, chunk in enumerate(chunks)
    ]

    index.add(matrix)
    faiss.write_index(index, str(index_path))
    chunks_path.write_text(
        json.dumps(existing + records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── Chunk inspection ──────────────────────────────────────────────────────────

def chunks_for_document(knowledge_base_dir: Path, relative_path: str) -> dict:
    chunks_path = knowledge_base_dir / settings.VECTOR_STORE_NAME / "chunks.json"
    if not chunks_path.exists():
        return {"source": relative_path, "chunks": []}

    records = json.loads(chunks_path.read_text(encoding="utf-8"))
    chunks = sorted(
        (
            {"id": r["id"], "chunk": r["metadata"].get("chunk", 0), "text": r["text"], "metadata": r["metadata"]}
            for r in records
            if r.get("metadata", {}).get("source") == relative_path
        ),
        key=lambda x: x["chunk"],
    )
    return {"source": relative_path, "chunks": chunks}


# ── Full pipeline ─────────────────────────────────────────────────────────────

async def ingest_document(
    knowledge_base_dir: Path,
    document_path: Path,
    relative_path: str,
    content: bytes,
) -> dict:
    text = parse_document(document_path.name, content)
    if not text.strip():
        raise ValueError("Document does not contain extractable text.")

    chunks = await split_text(text, knowledge_base_dir, relative_path)
    if not chunks:
        raise ValueError("Chunking produced no usable text.")

    vectors = await embed_chunks(chunks)
    store_vectors(knowledge_base_dir, relative_path, chunks, vectors, content)

    return {"chunks": len(chunks), "embedding_model": settings.EMBED_MODEL}
