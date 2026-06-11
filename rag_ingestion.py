from rag_chunking import (
    AGENTIC_CHUNK_INTERACTION_LOG,
    AGENTIC_CHUNK_MAX_CHARS,
    AGENTIC_CHUNK_MODEL,
    AGENTIC_CHUNK_TARGET_CHARS,
    AGENTIC_CHUNK_TIMEOUT_SECONDS,
    AGENTIC_CHUNK_WINDOW_SIZE,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    fallback_split_text,
    split_text,
)
from rag_config import (
    BM25_INDEX_NAME,
    EMBED_TIMEOUT_SECONDS,
    MAX_CONTEXT_TOKENS,
    OLLAMA_CHUNK_URL,
    OLLAMA_EMBED_MODEL,
    OLLAMA_EMBED_URL,
    RERANKER_DEVICE,
    RERANKER_MODEL,
    SUPPORTED_DOCUMENT_EXTENSIONS,
    VECTOR_STORE_NAME,
)
from rag_embedding import embed_chunks, embed_query
from rag_parsing import parse_docx, parse_document, parse_pdf, supported_document_types
from rag_retrieval import hybrid_retrieval, retrieve_context
from rag_store import (
    append_document_chunks,
    bm25_search,
    build_bm25_index,
    build_context,
    chunk_identity,
    count_tokens,
    chunks_for_document,
    faiss_search,
    get_reranker,
    load_bm25_index,
    rebuild_bm25_index,
    rerank_chunks,
    save_bm25_index,
    select_context,
    store_vectors,
    tokenize_for_bm25,
)


def _ingestion_result(relative_path: str, chunks: int, characters: int) -> dict:
    return {
        "source": relative_path,
        "chunks": chunks,
        "characters": characters,
        "embedding_model": OLLAMA_EMBED_MODEL,
        "chunking_model": AGENTIC_CHUNK_MODEL,
    }


async def ingest_document(
    knowledge_base_dir,
    document_path,
    relative_path: str,
    content: bytes,
) -> dict:
    return await ingest_document_with_progress(
        knowledge_base_dir,
        document_path,
        relative_path,
        content,
    )


async def ingest_document_with_progress(
    knowledge_base_dir,
    document_path,
    relative_path: str,
    content: bytes,
    on_progress=None,
) -> dict:
    async def report(phase: str, progress: float, message: str, **extra):
        if on_progress is not None:
            await on_progress({
                "phase": phase,
                "progress": progress,
                "message": message,
                **extra,
            })

    await report("parsing", 5.0, "Parsing document...")
    text = parse_document(document_path.name, content)
    if not text.strip():
        raise ValueError("Document did not contain any extractable text.")

    async def chunk_progress(fraction: float):
        progress = 5.0 + (fraction * 35.0)
        await report("chunking", progress, "Chunking document...")

    await report("chunking", 10.0, "Chunking document...")
    chunks = await split_text(
        text,
        knowledge_base_dir,
        relative_path,
        on_progress=chunk_progress,
    )
    if not chunks:
        raise ValueError("Document did not produce any chunks.")

    total_chunks = len(chunks)
    await report(
        "embedding",
        40.0,
        f"Indexing 0 of {total_chunks} chunks...",
        chunks_total=total_chunks,
        chunks_done=0,
    )

    for index, chunk in enumerate(chunks):
        vector = (await embed_chunks([chunk]))[0]
        await append_document_chunks(
            knowledge_base_dir,
            relative_path,
            chunk,
            vector,
            content,
            chunk_offset=index,
            rebuild_bm25=False,
        )
        chunks_done = index + 1
        progress = 40.0 + ((chunks_done / total_chunks) * 55.0)
        await report(
            "embedding",
            progress,
            f"Indexing {chunks_done} of {total_chunks} chunks...",
            chunks_total=total_chunks,
            chunks_done=chunks_done,
        )

    await rebuild_bm25_index(knowledge_base_dir)
    await report(
        "complete",
        100.0,
        "Document indexed and ready for Q&A",
        chunks_total=total_chunks,
        chunks_done=total_chunks,
    )

    return _ingestion_result(relative_path, total_chunks, len(text))

__all__ = [
    "AGENTIC_CHUNK_INTERACTION_LOG",
    "AGENTIC_CHUNK_MAX_CHARS",
    "AGENTIC_CHUNK_MODEL",
    "AGENTIC_CHUNK_TARGET_CHARS",
    "AGENTIC_CHUNK_TIMEOUT_SECONDS",
    "AGENTIC_CHUNK_WINDOW_SIZE",
    "BM25_INDEX_NAME",
    "CHUNK_OVERLAP",
    "CHUNK_SIZE",
    "EMBED_TIMEOUT_SECONDS",
    "MAX_CONTEXT_TOKENS",
    "OLLAMA_CHUNK_URL",
    "OLLAMA_EMBED_MODEL",
    "OLLAMA_EMBED_URL",
    "RERANKER_DEVICE",
    "RERANKER_MODEL",
    "SUPPORTED_DOCUMENT_EXTENSIONS",
    "VECTOR_STORE_NAME",
    "bm25_search",
    "build_bm25_index",
    "build_context",
    "chunk_identity",
    "count_tokens",
    "chunks_for_document",
    "embed_chunks",
    "embed_query",
    "faiss_search",
    "fallback_split_text",
    "get_reranker",
    "hybrid_retrieval",
    "ingest_document",
    "ingest_document_with_progress",
    "load_bm25_index",
    "parse_docx",
    "parse_document",
    "parse_pdf",
    "rerank_chunks",
    "retrieve_context",
    "save_bm25_index",
    "select_context",
    "split_text",
    "store_vectors",
    "supported_document_types",
    "tokenize_for_bm25",
]
