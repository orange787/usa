"""Async event bus for inter-agent communication."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Callable, Awaitable

from src.core.models import Event, EventType

logger = logging.getLogger(__name__)

EventHandler = Callable[[Event], Awaitable[None]]


class EventBus:
    """In-process async event bus.

    Supports subscribing to specific event types and wildcard subscriptions.
    Uses asyncio for async event dispatch.
    """

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[EventHandler]] = defaultdict(list)
        self._wildcard_handlers: list[EventHandler] = []
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._running = False
        self._task: asyncio.Task | None = None

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)
        logger.debug("Subscribed %s to %s", handler.__qualname__, event_type.value)

    def subscribe_all(self, handler: EventHandler) -> None:
        self._wildcard_handlers.append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    async def publish(self, event: Event) -> None:
        await self._queue.put(event)
        logger.debug("Published event: %s", event.type.value)

    def publish_sync(self, event: Event) -> None:
        """Non-async publish for use in sync contexts."""
        self._queue.put_nowait(event)

    async def _process_events(self) -> None:
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            handlers = list(self._handlers.get(event.type, []))
            handlers.extend(self._wildcard_handlers)

            for handler in handlers:
                try:
                    await handler(event)
                except Exception:
                    logger.exception(
                        "Error in event handler %s for %s",
                        handler.__qualname__,
                        event.type.value,
                    )

            self._queue.task_done()

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._process_events())
        logger.info("EventBus started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("EventBus stopped")

    async def wait_until_empty(self) -> None:
        await self._queue.join()
