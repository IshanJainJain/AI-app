import os

import httpx

from rag_config import EMBED_TIMEOUT_SECONDS, OLLAMA_EMBED_MODEL, OLLAMA_EMBED_URL


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


async def embed_query(query: str) -> list[float]:
    return (await embed_chunks([query]))[0]
