"""Tests for RequirementAnalystAgent."""

import pytest
from unittest.mock import AsyncMock

from src.agents.requirement_analyst import RequirementAnalystAgent
from src.core.models import Requirement, RequirementType, Priority


class FakeLLM:
    """Fake LLM that returns predefined responses."""

    def __init__(self, response: dict):
        self.response = response
        self.calls = []

    async def complete(self, prompt, system="", temperature=0.3, max_tokens=4096, response_format=None):
        self.calls.append(prompt)
        import json
        return json.dumps(self.response)

    async def complete_json(self, prompt, system="", temperature=0.3, max_tokens=4096):
        self.calls.append(prompt)
        return self.response


@pytest.mark.asyncio
async def test_extract_requirement():
    fake_llm = FakeLLM({
        "title": "Add daily login reward",
        "description": "Players should receive a reward for daily login",
        "type": "feature",
        "priority": "P1",
        "acceptance_criteria": ["Reward popup shows on login", "Streak counter works"],
        "background": "Increase retention",
        "affected_areas": ["login", "rewards"],
        "requester_notes": "",
    })

    analyst = RequirementAnalystAgent(fake_llm)
    messages = [
        {
            "id": "1",
            "user_name": "Ops Manager",
            "text": "我们需要每日登录奖励功能",
            "timestamp": "2024-01-01T10:00:00",
        },
    ]

    req = await analyst.extract_requirement(messages)

    assert req is not None
    assert req.title == "Add daily login reward"
    assert req.type == RequirementType.FEATURE
    assert req.priority == Priority.P1
    assert len(req.acceptance_criteria) == 2


@pytest.mark.asyncio
async def test_extract_requirement_empty_messages():
    analyst = RequirementAnalystAgent(FakeLLM({}))
    result = await analyst.extract_requirement([])
    assert result is None


@pytest.mark.asyncio
async def test_detect_conflicts():
    fake_llm = FakeLLM({
        "conflicts": [
            {"issue_number": 5, "reason": "Similar feature", "type": "duplicate"}
        ]
    })

    analyst = RequirementAnalystAgent(fake_llm)
    req = Requirement(title="Login reward", description="Daily login reward")
    existing = [
        {"number": 5, "title": "Daily check-in bonus"},
        {"number": 6, "title": "Unrelated feature"},
    ]

    conflicts = await analyst.detect_conflicts(req, existing)
    assert len(conflicts) == 1
    assert conflicts[0]["issue_number"] == 5


@pytest.mark.asyncio
async def test_generate_doc():
    analyst = RequirementAnalystAgent(FakeLLM({}))
    req = Requirement(
        title="Test Feature",
        description="A test feature",
        type=RequirementType.FEATURE,
        priority=Priority.P1,
        acceptance_criteria=["Works correctly"],
        background="Testing",
    )

    doc = await analyst.generate_doc(req)
    assert "# Test Feature" in doc
    assert "P1" in doc
    assert "Works correctly" in doc
