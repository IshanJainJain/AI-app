import hashlib
import json
import os
from io import BytesIO
from pathlib import Path

import httpx

SUPPORTED_DOCUMENT_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}

OLLAMA_EMBED_URL = os.getenv("OLLAMA_EMBED_URL", "http://localhost:11434/api/embeddings")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
EMBED_TIMEOUT_SECONDS = float(os.getenv("EMBED_TIMEOUT_SECONDS", "120"))
OLLAMA_CHUNK_URL = os.getenv("OLLAMA_AGENTIC_CHUNK_URL", "http://localhost:11434/api/generate")
AGENTIC_CHUNK_MODEL = os.getenv("AGENTIC_CHUNK_MODEL", "gemma3:1b")
AGENTIC_CHUNK_TIMEOUT_SECONDS = float(os.getenv("AGENTIC_CHUNK_TIMEOUT_SECONDS", "300"))
AGENTIC_CHUNK_TARGET_CHARS = int(os.getenv("AGENTIC_CHUNK_TARGET_CHARS", os.getenv("RAG_CHUNK_SIZE", "360")))
AGENTIC_CHUNK_MAX_CHARS = int(os.getenv("AGENTIC_CHUNK_MAX_CHARS", "1800"))
AGENTIC_CHUNK_WINDOW_SIZE = int(os.getenv("AGENTIC_CHUNK_WINDOW_SIZE", "5"))
CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "360"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "0"))
VECTOR_STORE_NAME = ".vector_store"


def supported_document_types() -> str:
    return ", ".join(sorted(SUPPORTED_DOCUMENT_EXTENSIONS))


def parse_document(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md"}:
        return content.decode("utf-8", errors="replace")
    if suffix == ".pdf":
        return parse_pdf(content)
    if suffix == ".docx":
        return parse_docx(content)
    raise ValueError(f"Unsupported document type. Use: {supported_document_types()}")


def parse_pdf(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Install pypdf to ingest PDF documents.") from exc

    reader = PdfReader(BytesIO(content))
    return "\n\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()


def parse_docx(content: bytes) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("Install python-docx to ingest DOCX documents.") from exc

    document = Document(BytesIO(content))
    return "\n".join(paragraph.text for paragraph in document.paragraphs).strip()


async def split_text(text: str) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []

    base_chunks = fallback_split_text(normalized, CHUNK_SIZE, CHUNK_OVERLAP)
    if not base_chunks:
        return []

    refined_chunks = []
    carryover = []
    async with httpx.AsyncClient(timeout=AGENTIC_CHUNK_TIMEOUT_SECONDS) as client:
        for start in range(0, len(base_chunks), AGENTIC_CHUNK_WINDOW_SIZE):
            window = base_chunks[start:start + AGENTIC_CHUNK_WINDOW_SIZE]
            result = await agentic_refine_chunk_window(client, carryover, window)
            if result is None:
                refined_chunks.extend(carryover + window)
                carryover = []
                continue
            refined_chunks.extend(result["final_chunks"])
            carryover = result["carryover"]

    refined_chunks.extend(carryover)
    return normalize_agentic_chunks([chunk for chunk in refined_chunks if chunk])


def normalize_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


async def agentic_refine_chunk_window(
    client: httpx.AsyncClient,
    carryover: list[str],
    window: list[str],
) -> dict | None:
    prompt = build_agentic_chunk_prompt(carryover, window)
    try:
        response = await client.post(
            OLLAMA_CHUNK_URL,
            json={
                "model": AGENTIC_CHUNK_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0,
                    "num_ctx": 8192,
                },
            },
        )
        response.raise_for_status()
        return parse_agentic_chunk_response(response.json().get("response", ""))
    except Exception:
        return None


def build_agentic_chunk_prompt(carryover: list[str], window: list[str]) -> str:
    carryover_text = format_numbered_chunks(carryover, "C")
    window_text = format_numbered_chunks(window, "N")
    return f"""You are refining confidential company knowledge-base chunks for retrieval.

You will receive:
- CARRYOVER chunks: text from the previous window that was not finalized because it may need to merge with upcoming context.
- NEW chunks: the next {AGENTIC_CHUNK_WINDOW_SIZE} recursive character chunks.

Decide whether these chunks should stay separate, be combined, or be broken further.
Rules:
- Preserve the original wording exactly.
- Do not summarize, rewrite, redact, invent, or omit content.
- Keep related clauses, definitions, exceptions, and steps together.
- Prefer chunks around {AGENTIC_CHUNK_TARGET_CHARS} characters.
- Do not exceed {AGENTIC_CHUNK_MAX_CHARS} characters unless a single paragraph is longer.
- If text at the end may need the next window to form a complete semantic chunk, put it in "carryover".
- It is okay to carry over multiple chunks. For example, if 7 recursive chunks belong together, carry over the first 5 from one call and combine them after the next window arrives.
- "final_chunks" must contain only text that is complete enough to embed now.
- "carryover" must contain only trailing text that should wait for the next window.
- Return only valid JSON in this exact shape:
{{"final_chunks":["complete chunk"],"carryover":["trailing chunk that may continue"]}}

CARRYOVER chunks:
{carryover_text or "(none)"}

NEW chunks:
{window_text}"""


def format_numbered_chunks(chunks: list[str], prefix: str) -> str:
    return "\n\n".join(
        f"[{prefix}{index + 1}]\n{chunk}"
        for index, chunk in enumerate(chunks)
    )


def parse_agentic_chunk_response(response_text: str) -> dict | None:
    response_text = response_text.strip()
    if response_text.startswith("```"):
        response_text = response_text.strip("`")
        if response_text.startswith("json"):
            response_text = response_text[4:].strip()

    start = response_text.find("{")
    end = response_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        payload = json.loads(response_text[start:end + 1])
    except json.JSONDecodeError:
        return None

    final_chunks = payload.get("final_chunks", [])
    carryover = payload.get("carryover", [])
    if not isinstance(final_chunks, list) or not isinstance(carryover, list):
        return None

    return {
        "final_chunks": clean_chunk_list(final_chunks),
        "carryover": clean_chunk_list(carryover),
    }


def clean_chunk_list(chunks: list) -> list[str]:
    return [chunk.strip() for chunk in chunks if isinstance(chunk, str) and chunk.strip()]


def normalize_agentic_chunks(chunks: list[str]) -> list[str]:
    normalized = []
    for chunk in chunks:
        if len(chunk) <= AGENTIC_CHUNK_MAX_CHARS:
            normalized.append(chunk)
        else:
            normalized.extend(fallback_split_text(chunk, AGENTIC_CHUNK_MAX_CHARS, 0))
    return normalized


def fallback_split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    normalized = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    if not normalized:
        return []

    chunks = recursive_split(normalized, chunk_size, ["\n\n", "\n", ". ", " ", ""])
    merged = []
    current = ""

    for chunk in chunks:
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
            overlap_text = current[-overlap:] if overlap > 0 else ""
            current = f"{overlap_text}\n{chunk}".strip()

    if current:
        merged.append(current.strip())

    return [chunk for chunk in merged if chunk]


def recursive_split(text: str, chunk_size: int, separators: list[str]) -> list[str]:
    if len(text) <= chunk_size:
        return [text.strip()]

    separator = separators[0]
    remaining = separators[1:]
    if separator == "":
        return [text[index:index + chunk_size].strip() for index in range(0, len(text), chunk_size)]

    pieces = text.split(separator)
    if len(pieces) == 1:
        return recursive_split(text, chunk_size, remaining)

    chunks = []
    current = ""
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        candidate = piece if not current else f"{current}{separator}{piece}"
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        if current:
            chunks.extend(recursive_split(current, chunk_size, remaining))
        current = piece

    if current:
        chunks.extend(recursive_split(current, chunk_size, remaining))
    return chunks


async def embed_chunks(chunks: list[str]) -> list[list[float]]:
    vectors = []
    async with httpx.AsyncClient(timeout=EMBED_TIMEOUT_SECONDS) as client:
        for chunk in chunks:
            response = await client.post(
                OLLAMA_EMBED_URL,
                json={"model": OLLAMA_EMBED_MODEL, "prompt": chunk},
            )
            response.raise_for_status()
            data = response.json()
            embedding = data.get("embedding")
            if not embedding:
                raise RuntimeError("Embedding model returned an empty vector.")
            vectors.append(embedding)
    return vectors


async def ingest_document(
    knowledge_base_dir: Path,
    document_path: Path,
    relative_path: str,
    content: bytes,
) -> dict:
    text = parse_document(document_path.name, content)
    chunks = await split_text(text)
    if not chunks:
        raise ValueError("Document does not contain extractable text.")

    vectors = await embed_chunks(chunks)
    store_vectors(knowledge_base_dir, relative_path, chunks, vectors, content)
    return {
        "chunks": len(chunks),
        "embedding_model": OLLAMA_EMBED_MODEL,
    }


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

    vector_store_dir = knowledge_base_dir / VECTOR_STORE_NAME
    vector_store_dir.mkdir(exist_ok=True)
    index_path = vector_store_dir / "faiss.index"
    chunks_path = vector_store_dir / "chunks.json"

    matrix = np.array(vectors, dtype="float32")
    faiss.normalize_L2(matrix)

    if index_path.exists():
        index = faiss.read_index(str(index_path))
        if index.d != matrix.shape[1]:
            raise RuntimeError("Existing FAISS index dimension does not match the embedding model.")
    else:
        index = faiss.IndexFlatIP(matrix.shape[1])

    existing_chunks = []
    if chunks_path.exists():
        existing_chunks = json.loads(chunks_path.read_text(encoding="utf-8"))

    document_hash = hashlib.sha256(content).hexdigest()
    start_index = len(existing_chunks)
    records = []
    for offset, chunk in enumerate(chunks):
        records.append({
            "id": start_index + offset,
            "text": chunk,
            "metadata": {
                "source": relative_path,
                "chunk": offset,
                "sha256": document_hash,
                "embedding_model": OLLAMA_EMBED_MODEL,
                "chunking_model": AGENTIC_CHUNK_MODEL,
            },
        })

    index.add(matrix)
    faiss.write_index(index, str(index_path))
    chunks_path.write_text(
        json.dumps(existing_chunks + records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def chunks_for_document(knowledge_base_dir: Path, relative_path: str) -> dict:
    chunks_path = knowledge_base_dir / VECTOR_STORE_NAME / "chunks.json"
    if not chunks_path.exists():
        return {"source": relative_path, "chunks": []}

    records = json.loads(chunks_path.read_text(encoding="utf-8"))
    chunks = [
        {
            "id": record["id"],
            "chunk": record["metadata"].get("chunk", 0),
            "text": record["text"],
            "metadata": record["metadata"],
        }
        for record in records
        if record.get("metadata", {}).get("source") == relative_path
    ]
    chunks.sort(key=lambda item: item["chunk"])
    return {"source": relative_path, "chunks": chunks}
