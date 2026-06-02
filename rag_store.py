import hashlib
import json
import pickle
import re
from pathlib import Path

from rag_config import BM25_INDEX_NAME, OLLAMA_EMBED_MODEL, VECTOR_STORE_NAME


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
    all_chunks = existing_chunks + records
    chunks_path.write_text(json.dumps(all_chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    save_bm25_index(knowledge_base_dir, build_bm25_index(all_chunks))


def tokenize_for_bm25(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_]+", text.lower())


def build_bm25_index(chunks: list[dict]) -> dict:
    try:
        from rank_bm25 import BM25Okapi
    except ImportError as exc:
        raise RuntimeError("Install rank-bm25 to build the BM25 index.") from exc

    tokenized_corpus = [tokenize_for_bm25(chunk["text"]) for chunk in chunks]
    return {
        "bm25": BM25Okapi(tokenized_corpus),
        "chunks": chunks,
    }


def save_bm25_index(knowledge_base_dir: Path, bm25_index: dict):
    vector_store_dir = knowledge_base_dir / VECTOR_STORE_NAME
    vector_store_dir.mkdir(exist_ok=True)
    with (vector_store_dir / BM25_INDEX_NAME).open("wb") as handle:
        pickle.dump(bm25_index, handle)


def load_bm25_index(knowledge_base_dir: Path) -> dict:
    index_path = knowledge_base_dir / VECTOR_STORE_NAME / BM25_INDEX_NAME
    if not index_path.exists():
        raise FileNotFoundError("BM25 index has not been built yet.")
    with index_path.open("rb") as handle:
        return pickle.load(handle)


def bm25_search(query: str, k: int, knowledge_base_dir: Path) -> list[dict]:
    bm25_index = load_bm25_index(knowledge_base_dir)
    scores = bm25_index["bm25"].get_scores(tokenize_for_bm25(query))
    ranked_indices = sorted(range(len(scores)), key=lambda index: scores[index], reverse=True)
    results = []
    for index in ranked_indices[:k]:
        chunk = bm25_index["chunks"][index]
        results.append({
            "score": float(scores[index]),
            "text": chunk["text"],
            "metadata": chunk["metadata"],
        })
    return results


def chunks_for_document(knowledge_base_dir: Path, relative_path: str) -> list[dict]:
    chunks_path = knowledge_base_dir / VECTOR_STORE_NAME / "chunks.json"
    if not chunks_path.exists():
        return []

    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    return [
        chunk
        for chunk in chunks
        if chunk.get("metadata", {}).get("source") == relative_path
    ]


async def faiss_search(query: str, k: int, knowledge_base_dir: Path) -> list[dict]:
    try:
        import faiss
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("Install faiss-cpu and numpy to search the FAISS index.") from exc

    from rag_embedding import embed_query

    vector_store_dir = knowledge_base_dir / VECTOR_STORE_NAME
    index_path = vector_store_dir / "faiss.index"
    chunks_path = vector_store_dir / "chunks.json"
    if not index_path.exists() or not chunks_path.exists():
        raise FileNotFoundError("FAISS index has not been built yet.")

    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    if not chunks:
        return []

    index = faiss.read_index(str(index_path))
    query_vector = np.array([await embed_query(query)], dtype="float32")
    faiss.normalize_L2(query_vector)

    scores, indices = index.search(query_vector, min(k, len(chunks)))
    results = []
    for score, index_id in zip(scores[0], indices[0]):
        if index_id < 0:
            continue
        chunk = chunks[int(index_id)]
        results.append({
            "score": float(score),
            "text": chunk["text"],
            "metadata": chunk["metadata"],
        })
    return results


def chunk_identity(result: dict) -> tuple:
    metadata = result.get("metadata", {})
    return (
        metadata.get("source"),
        metadata.get("chunk"),
        result.get("text"),
    )


def get_reranker():
    try:
        from FlagEmbedding import FlagReranker
    except ImportError as exc:
        raise RuntimeError("Install FlagEmbedding to use bge-reranker-base reranking.") from exc

    reranker = getattr(get_reranker, "_cached", None)
    if reranker is not None:
        return reranker

    from rag_config import RERANKER_DEVICE, RERANKER_MODEL

    reranker = FlagReranker(RERANKER_MODEL, use_fp16=False, device=RERANKER_DEVICE)
    get_reranker._cached = reranker
    return reranker


def rerank_chunks(query: str, chunks: list[dict], top_n: int) -> list[dict]:
    if not chunks:
        return []

    reranker = get_reranker()
    pairs = [[query, chunk.get("text", "")] for chunk in chunks]
    scores = reranker.compute_score(pairs)

    ranked = sorted(
        (
            {**chunk, "score": float(score)}
            for chunk, score in zip(chunks, scores)
        ),
        key=lambda item: item["score"],
        reverse=True,
    )
    return ranked[:top_n]


def count_tokens(text: str) -> int:
    try:
        import tiktoken
    except ImportError as exc:
        raise RuntimeError("Install tiktoken to use token-budget context selection.") from exc

    try:
        encoder = tiktoken.encoding_for_model("gpt-4o-mini")
    except Exception:
        encoder = tiktoken.get_encoding("cl100k_base")
    return len(encoder.encode(text))


def select_context(chunks: list[dict], max_tokens: int) -> list[dict]:
    selected = []
    used_tokens = 0

    for chunk in chunks:
        chunk_tokens = count_tokens(chunk.get("text", ""))
        if selected and used_tokens + chunk_tokens > max_tokens:
            break
        if not selected and chunk_tokens > max_tokens:
            selected.append(chunk)
            break
        selected.append(chunk)
        used_tokens += chunk_tokens

    return selected


def build_context(chunks: list[dict]) -> str:
    parts = []
    for chunk in chunks:
        metadata = chunk.get("metadata", {})
        source = metadata.get("source", "unknown")
        chunk_id = metadata.get("chunk", chunk.get("chunk", 0))
        text = chunk.get("text", "")
        parts.append(
            f"[Source: {source}]\n"
            f"[Chunk: {chunk_id}]\n\n"
            f"{text}"
        )
    return "\n\n".join(parts)


async def retrieve_context(query: str, knowledge_base_dir: Path) -> str:
    faiss_results = await faiss_search(query, 20, knowledge_base_dir)
    bm25_results = bm25_search(query, 20, knowledge_base_dir)

    candidates = []
    seen = set()
    for result in faiss_results + bm25_results:
        identity = chunk_identity(result)
        if identity in seen:
            continue
        seen.add(identity)
        candidates.append(result)

    reranked = rerank_chunks(query, candidates, top_n=len(candidates))
    selected = select_context(reranked, 6000)
    return build_context(selected)
