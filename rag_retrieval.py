from pathlib import Path

from rag_store import (
    bm25_search,
    build_context,
    chunk_identity,
    faiss_search,
    rerank_chunks,
    select_context,
)


async def hybrid_retrieval(query: str, k: int, knowledge_base_dir: Path) -> list[dict]:
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

    return candidates[:k]


async def retrieve_context(query: str, knowledge_base_dir: Path, max_tokens: int = 6000) -> str:
    candidates = await hybrid_retrieval(query, 20, knowledge_base_dir)
    reranked = rerank_chunks(query, candidates, top_n=len(candidates))
    selected = select_context(reranked, max_tokens)
    return build_context(selected)
