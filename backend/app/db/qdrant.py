"""Shared Qdrant client factory — single construction point for both ingestion and admin."""
from app.config import settings


def get_qdrant_client(timeout: float = 30):
    """Return a QdrantClient configured from settings. Raises ImportError if qdrant-client is not installed."""
    from qdrant_client import QdrantClient
    return QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY or None,
        timeout=timeout,
    )
