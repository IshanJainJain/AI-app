"""Knowledge Base MCP adapter — exposes KB search as an agent tool."""
import json
import logging
from pathlib import Path
from typing import List

import numpy as np

from app.config import settings
from app.mcp.base import MCPToolBase, ToolDefinition, ToolCallResult

logger = logging.getLogger(__name__)

_PARAMS_SEARCH = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Natural-language query to search the knowledge base",
        },
        "top_k": {
            "type": "integer",
            "description": "Number of chunks to return (default 5)",
            "default": 5,
        },
    },
    "required": ["query"],
}

_PARAMS_DOC_INFO = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Relative path to the document inside the knowledge base",
        },
    },
    "required": ["path"],
}


class KnowledgeBaseAdapter(MCPToolBase):
    def __init__(self):
        super().__init__(name="knowledge_base", description="Search and inspect the local knowledge base")

    def get_tools(self) -> List[ToolDefinition]:
        return [
            ToolDefinition(
                name="search_knowledge_base",
                description="Semantic search over all indexed knowledge-base documents. "
                            "Use this when the user's question may be answered by stored documents.",
                parameters=_PARAMS_SEARCH,
            ),
            ToolDefinition(
                name="get_document_info",
                description="Return the indexed chunks for a specific document path.",
                parameters=_PARAMS_DOC_INFO,
            ),
        ]

    async def execute(self, tool_name: str, params: dict) -> ToolCallResult:
        if tool_name == "search_knowledge_base":
            return await self._search(params.get("query", ""), params.get("top_k", 5))
        if tool_name == "get_document_info":
            return await self._doc_info(params.get("path", ""))
        return ToolCallResult(success=False, error=f"Unknown tool: {tool_name}")

    async def _search(self, query: str, top_k: int) -> ToolCallResult:
        try:
            import faiss
            kb_dir = Path(settings.KNOWLEDGE_BASE_DIR)
            vector_dir = kb_dir / settings.VECTOR_STORE_NAME
            index_path = vector_dir / "faiss.index"
            chunks_path = vector_dir / "chunks.json"

            if not index_path.exists() or not chunks_path.exists():
                return ToolCallResult(success=True, data={"chunks": [], "note": "Knowledge base is empty"})

            # Embed the query
            embedding = await self._embed_query(query)
            if embedding is None:
                return ToolCallResult(success=False, error="Could not embed query")

            index = faiss.read_index(str(index_path))
            vec = np.array([embedding], dtype=np.float32)
            faiss.normalize_L2(vec)
            k = min(top_k, index.ntotal)
            if k == 0:
                return ToolCallResult(success=True, data={"chunks": []})

            scores, indices = index.search(vec, k)
            with open(chunks_path) as f:
                all_chunks = json.load(f)

            results = []
            for score, idx in zip(scores[0].tolist(), indices[0].tolist()):
                if idx < 0 or idx >= len(all_chunks):
                    continue
                chunk = all_chunks[idx]
                results.append({
                    "score": round(score, 4),
                    "text": chunk["text"],
                    "source": chunk["metadata"].get("source", ""),
                    "chunk_index": chunk["metadata"].get("chunk", idx),
                })

            return ToolCallResult(success=True, data={"query": query, "chunks": results})
        except Exception as exc:
            logger.exception("KB search failed")
            return ToolCallResult(success=False, error=str(exc))

    async def _doc_info(self, path: str) -> ToolCallResult:
        try:
            kb_dir = Path(settings.KNOWLEDGE_BASE_DIR)
            vector_dir = kb_dir / settings.VECTOR_STORE_NAME
            chunks_path = vector_dir / "chunks.json"

            if not chunks_path.exists():
                return ToolCallResult(success=True, data={"chunks": []})

            with open(chunks_path) as f:
                all_chunks = json.load(f)

            doc_chunks = [c for c in all_chunks if c["metadata"].get("source") == path]
            return ToolCallResult(success=True, data={"path": path, "chunk_count": len(doc_chunks), "chunks": doc_chunks})
        except Exception as exc:
            return ToolCallResult(success=False, error=str(exc))

    async def _embed_query(self, text: str) -> list | None:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.EMBED_API_KEY, base_url=settings.EMBED_BASE_URL)
            response = await client.embeddings.create(
                model=settings.EMBED_MODEL,
                input=text,
            )
            return response.data[0].embedding
        except Exception as exc:
            logger.error("Embedding request failed: %s", exc)
            return None
