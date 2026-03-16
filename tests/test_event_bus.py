"""Tests for the EventBus."""

import asyncio
import pytest

from src.core.event_bus import EventBus
from src.core.models import Event, EventType


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.mark.asyncio
async def test_subscribe_and_publish(event_bus):
    received = []

    async def handler(event: Event):
        received.append(event)

    event_bus.subscribe(EventType.TG_MESSAGE_RECEIVED, handler)
    await event_bus.start()

    await event_bus.publish(Event(
        type=EventType.TG_MESSAGE_RECEIVED,
        data={"text": "hello"},
    ))

    await asyncio.sleep(0.1)
    await event_bus.stop()

    assert len(received) == 1
    assert received[0].data["text"] == "hello"


@pytest.mark.asyncio
async def test_wildcard_handler(event_bus):
    received = []

    async def handler(event: Event):
        received.append(event.type)

    event_bus.subscribe_all(handler)
    await event_bus.start()

    await event_bus.publish(Event(type=EventType.TG_MESSAGE_RECEIVED))
    await event_bus.publish(Event(type=EventType.GH_ISSUE_CREATED))

    await asyncio.sleep(0.1)
    await event_bus.stop()

    assert len(received) == 2


@pytest.mark.asyncio
async def test_handler_error_does_not_crash_bus(event_bus):
    """An exception in one handler should not prevent others from running."""
    received = []

    async def bad_handler(event: Event):
        raise ValueError("boom")

    async def good_handler(event: Event):
        received.append(event)

    event_bus.subscribe(EventType.TG_MESSAGE_RECEIVED, bad_handler)
    event_bus.subscribe(EventType.TG_MESSAGE_RECEIVED, good_handler)
    await event_bus.start()

    await event_bus.publish(Event(type=EventType.TG_MESSAGE_RECEIVED))

    await asyncio.sleep(0.1)
    await event_bus.stop()

    assert len(received) == 1


@pytest.mark.asyncio
async def test_unsubscribe(event_bus):
    received = []

    async def handler(event: Event):
        received.append(event)

    event_bus.subscribe(EventType.TG_MESSAGE_RECEIVED, handler)
    event_bus.unsubscribe(EventType.TG_MESSAGE_RECEIVED, handler)
    await event_bus.start()

    await event_bus.publish(Event(type=EventType.TG_MESSAGE_RECEIVED))

    await asyncio.sleep(0.1)
    await event_bus.stop()

    assert len(received) == 0
