"""
Celery tasks.

ingest_document_task — async RAG ingestion run synchronously in the worker.
cleanup_old_tasks    — periodic cleanup of old cache entries.
"""
import asyncio
import logging
from pathlib import Path

from app.workers.celery_app import celery_app
from app.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.workers.tasks.ingest_document_task", max_retries=2)
def ingest_document_task(self, kb_dir: str, target_path: str, relative_path: str, content_hex: str):
    """
    Run RAG ingestion for an uploaded document.
    content_hex is the raw file bytes encoded as a hex string.
    """
    try:
        from app.rag.ingestion import ingest_document
        content = bytes.fromhex(content_hex)
        result = asyncio.run(
            ingest_document(Path(kb_dir), Path(target_path), relative_path, content)
        )
        logger.info("Ingested %s: %d chunks", relative_path, result.get("chunks", 0))
        return result
    except Exception as exc:
        logger.error("Ingestion failed for %s: %s", relative_path, exc)
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="app.workers.tasks.cleanup_old_tasks")
def cleanup_old_tasks():
    """Remove cache entries older than 24 hours."""
    try:
        import redis as sync_redis
        r = sync_redis.from_url(settings.REDIS_URL)
        keys = r.keys("task:*")
        cleaned = 0
        for key in keys:
            ttl = r.ttl(key)
            if ttl < 0:
                r.delete(key)
                cleaned += 1
        logger.info("Cleaned up %d stale task cache entries", cleaned)
    except Exception as exc:
        logger.warning("Cleanup task failed: %s", exc)
