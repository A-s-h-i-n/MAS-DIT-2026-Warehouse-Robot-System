"""Event bus for the MAS.

Every agent action is logged here. The bus keeps a bounded history (for the
`/events` REST endpoint) and fans messages out to live subscribers (the
WebSocket connections that drive the dashboard in real time). Subscribers
receive dict envelopes of two kinds: ``{"type": "event", ...}`` for agent
actions and ``{"type": "state", ...}`` for full world snapshots each tick.
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque

from backend.config import settings
from backend.domain import Event

logger = logging.getLogger("wms.events")


def event_to_dict(e: Event) -> dict:
    return {
        "tick": e.tick,
        "agent": e.agent,
        "type": e.type,
        "message": e.message,
        "data": e.data,
    }


class EventBus:
    def __init__(self, maxlen: int = settings.MAX_EVENTS) -> None:
        self._history: deque[Event] = deque(maxlen=maxlen)
        self._subscribers: set[asyncio.Queue] = set()

    # --------------------------------------------------------------- emit
    def emit(self, tick: int, agent: str, type: str, message: str, **data) -> Event:
        """Record an agent action and broadcast it to live subscribers."""
        event = Event(tick=tick, agent=agent, type=type, message=message, data=data)
        self._history.append(event)
        logger.info("[t=%s] %-9s %-16s %s", tick, agent, type, message)
        self._broadcast({"type": "event", "event": event_to_dict(event)})
        return event

    def broadcast_state(self, snapshot: dict) -> None:
        """Push a full world snapshot to subscribers (once per tick)."""
        self._broadcast({"type": "state", "state": snapshot})

    def _broadcast(self, message: dict) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                # Slow consumer — drop this message for that subscriber only.
                pass

    # ------------------------------------------------------------- history
    def history(self, limit: int | None = None) -> list[dict]:
        events = list(self._history)
        if limit is not None:
            events = events[-limit:]
        return [event_to_dict(e) for e in events]

    # --------------------------------------------------------- subscriptions
    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)


# Shared singleton used across the whole backend.
bus = EventBus()
