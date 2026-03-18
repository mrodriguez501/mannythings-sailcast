"""
SSE Event Bus

Lightweight asyncio pub/sub so the scheduler can notify all connected
SSE clients when a data refresh completes. Each SSE connection subscribes
via an asyncio.Queue; the bus fans out events to all queues.
"""

import asyncio
import logging
from datetime import UTC, datetime

logger = logging.getLogger("sailcast.events")


class EventBus:
    def __init__(self):
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(q)
        logger.debug("SSE subscriber added (%d total)", len(self._subscribers))
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)
        logger.debug("SSE subscriber removed (%d remaining)", len(self._subscribers))

    def publish(self, event: str = "refresh", data: dict | None = None) -> None:
        payload = data or {"generatedAt": datetime.now(UTC).isoformat()}
        msg = {"event": event, **payload}
        for q in self._subscribers:
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                logger.warning("SSE queue full, dropping event for one subscriber")


event_bus = EventBus()
