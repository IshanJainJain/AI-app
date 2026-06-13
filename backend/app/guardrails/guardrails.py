"""
Chat guardrails — content safety and rate limiting.

The pipeline is called before each agent tool execution and before
the final response is sent to the user.
"""
import logging
import time
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)

# ── Simple rate limiter (in-memory) ──────────────────────────────────────────

_rate_store: dict[str, list[float]] = defaultdict(list)
RATE_WINDOW_SECONDS = 60
RATE_MAX_MESSAGES = 60  # per user per minute


def _check_rate_limit(user_id: str) -> bool:
    now = time.monotonic()
    window = _rate_store[user_id]
    window[:] = [t for t in window if now - t < RATE_WINDOW_SECONDS]
    if len(window) >= RATE_MAX_MESSAGES:
        return False
    window.append(now)
    return True


# ── Blocked patterns ──────────────────────────────────────────────────────────

_BLOCKED_KEYWORDS = {
    "ignore previous instructions",
    "ignore all instructions",
    "disregard your instructions",
    "you are now",
    "jailbreak",
    "dan mode",
}


def _content_check(text: str) -> Optional[str]:
    lower = text.lower()
    for kw in _BLOCKED_KEYWORDS:
        if kw in lower:
            return f"Message blocked: contains prohibited pattern '{kw}'"
    return None


# ── Public pipeline ───────────────────────────────────────────────────────────

class ChatGuardrails:
    def check_message(self, user_id: str, content: str) -> dict:
        """
        Returns {"allowed": bool, "reason": str | None}.
        Called before processing any user message.
        """
        if not _check_rate_limit(user_id):
            return {"allowed": False, "reason": "Rate limit exceeded — please slow down."}

        reason = _content_check(content)
        if reason:
            return {"allowed": False, "reason": reason}

        return {"allowed": True, "reason": None}

    def check_tool_call(self, tool_name: str, params: dict, user_id: str) -> dict:
        """Called before each agent tool execution."""
        return {"allowed": True, "reason": None}

    def check_response(self, response: str, user_id: str) -> dict:
        """Called before sending the agent response to the client."""
        return {"allowed": True, "reason": None}


guardrails = ChatGuardrails()
