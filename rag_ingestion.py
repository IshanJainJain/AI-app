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
CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "1200"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "200"))
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


def split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
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
    chunks = split_text(text)
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
