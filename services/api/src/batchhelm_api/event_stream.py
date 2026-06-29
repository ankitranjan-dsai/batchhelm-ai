"""Live agent event streaming.

The orchestrator emits :class:`AgentRunEvent` objects as agents start, reason,
finish, retry, or resolve conflicts. ``RunEventChannel`` lets an HTTP handler
fan those events out over Server-Sent Events while the run is still in flight,
so the dashboard shows a live mission-control timeline rather than a single
end-of-run payload.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from batchhelm_api.models import AgentRunEvent


class RunEventChannel:
    """An async queue of run events with a sentinel-based close."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[AgentRunEvent | None] = asyncio.Queue()
        self._closed = False

    async def emit(self, event: AgentRunEvent) -> None:
        if not self._closed:
            await self._queue.put(event)

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            await self._queue.put(None)

    async def __aiter__(self) -> AsyncIterator[AgentRunEvent]:
        while True:
            event = await self._queue.get()
            if event is None:
                return
            yield event


def sse_pack(event: AgentRunEvent) -> str:
    """Render an event as a Server-Sent Events frame."""

    payload = event.model_dump_json()
    return f"event: {event.type.value}\ndata: {payload}\n\n"
