import asyncio
import os


class OllamaPriorityGate:
    """Give user-facing Ollama calls priority over background ingestion work."""

    def __init__(self):
        self._active_user_requests = 0
        self._mutex = asyncio.Lock()
        self._background_allowed = asyncio.Event()
        self._background_allowed.set()
        self._background_poll_seconds = float(os.getenv("OLLAMA_BACKGROUND_POLL_SECONDS", "0.25"))

    @property
    def user_requests_active(self) -> bool:
        return self._active_user_requests > 0

    async def begin_user_request(self):
        async with self._mutex:
            self._active_user_requests += 1
            self._background_allowed.clear()

    async def end_user_request(self):
        async with self._mutex:
            self._active_user_requests = max(0, self._active_user_requests - 1)
            if self._active_user_requests == 0:
                self._background_allowed.set()

    def user_session(self) -> "_UserSession":
        return _UserSession(self)

    async def wait_for_background_turn(self):
        """Pause background Ollama work while user queries are in flight."""
        while True:
            await self._background_allowed.wait()
            async with self._mutex:
                if self._active_user_requests == 0:
                    return
            await asyncio.sleep(self._background_poll_seconds)


class _UserSession:
    def __init__(self, gate: OllamaPriorityGate):
        self._gate = gate

    async def __aenter__(self):
        await self._gate.begin_user_request()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._gate.end_user_request()
        return False


ollama_gate = OllamaPriorityGate()
