"""Tests for data models."""

from src.core.models import (
    Requirement,
    RequirementType,
    Priority,
    RequirementStatus,
    ChatMessage,
    MessageSource,
    Event,
    EventType,
)


def test_requirement_defaults():
    req = Requirement(title="Test", description="A test requirement")
    assert req.type == RequirementType.FEATURE
    assert req.priority == Priority.P2
    assert req.status == RequirementStatus.DRAFT
    assert req.acceptance_criteria == []
    assert req.github_issue_number is None


def test_requirement_full():
    req = Requirement(
        title="Add login",
        description="Add OAuth login",
        type=RequirementType.FEATURE,
        priority=Priority.P1,
        acceptance_criteria=["User can login", "User can logout"],
        background="Users need authentication",
    )
    assert req.title == "Add login"
    assert len(req.acceptance_criteria) == 2


def test_chat_message():
    msg = ChatMessage(
        id="123",
        source=MessageSource.TELEGRAM,
        chat_id="-1001234",
        user_id="456",
        user_name="Test User",
        text="Hello world",
    )
    assert msg.source == MessageSource.TELEGRAM
    assert msg.media_urls == []


def test_event_serialization():
    event = Event(
        type=EventType.TG_MESSAGE_RECEIVED,
        data={"text": "test"},
        source="test",
    )
    dumped = event.model_dump()
    assert dumped["type"] == "tg.message.received"
    assert dumped["data"]["text"] == "test"


def test_requirement_model_dump():
    req = Requirement(title="Test", description="Desc")
    data = req.model_dump()
    assert data["title"] == "Test"
    assert data["type"] == "feature"
    assert data["priority"] == "P2"
