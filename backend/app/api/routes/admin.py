"""Admin endpoints — KB health, reindex status."""
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


async def _qdrant_ping() -> bool:
    """Return True if Qdrant responds, False after 3 attempts with exponential backoff."""
    from app.db.qdrant import get_qdrant_client
    delay = 1.0
    for attempt in range(3):
        try:
            client = get_qdrant_client(timeout=5)
            await asyncio.to_thread(client.get_collections)
            return True
        except Exception:
            if attempt < 2:
                await asyncio.sleep(delay)
                delay *= 2
    return False


async def _qdrant_healthy() -> Optional[bool]:
    """None = not configured; True/False = configured and reachable/unreachable."""
    if not settings.QDRANT_URL:
        return None
    return await _qdrant_ping()


@router.get("/kb/health")
async def kb_health(current_user=Depends(get_current_user)):
    from app.db.mongodb import count_degraded_kb_docs
    degraded_count = await count_degraded_kb_docs()
    qdrant_ok = await _qdrant_healthy()
    return {
        "degraded_count": degraded_count,
        "qdrant_healthy": qdrant_ok,
    }
