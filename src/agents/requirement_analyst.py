"""Agent 2: Requirement Analyst Agent - LLM-powered requirement extraction."""

from __future__ import annotations

import logging
from typing import Any

from src.core.config import load_prompt, get_app_config
from src.core.models import Requirement, RequirementType, Priority
from src.services.llm.base import BaseLLM

logger = logging.getLogger(__name__)


class RequirementAnalystAgent:
    """Uses LLM to extract and analyze structured requirements from chat."""

    def __init__(self, llm: BaseLLM) -> None:
        self.llm = llm
        self.config = get_app_config()
        self._extract_prompt = load_prompt("requirement_extract")
        self._priority_prompt = load_prompt("priority_assess")

    # ── Skill: requirement_extract + message_summarize ────────────────────

    async def extract_requirement(
        self, messages: list[dict]
    ) -> Requirement | None:
        """Extract a structured requirement from chat messages."""
        if not messages:
            return None

        # Format messages for LLM
        conversation = self._format_messages(messages)

        system = self._extract_prompt
        prompt = f"## Chat Conversation\n\n{conversation}\n\n## Task\nExtract the requirement from the above conversation."

        try:
            temps = self.config.get("llm", {}).get("temperatures", {})
            result = await self.llm.complete_json(
                prompt=prompt,
                system=system,
                temperature=temps.get("requirement_extract", 0.3),
            )
        except Exception:
            logger.exception("Failed to extract requirement via LLM")
            return None

        # Map to Requirement model
        try:
            req_type = result.get("type", "feature")
            priority = result.get("priority", "P2")

            return Requirement(
                title=result.get("title", "Untitled Requirement"),
                description=result.get("description", ""),
                type=RequirementType(req_type) if req_type in RequirementType.__members__.values() else RequirementType.FEATURE,
                priority=Priority(priority) if priority in Priority.__members__.values() else Priority.P2,
                acceptance_criteria=result.get("acceptance_criteria", []),
                background=result.get("background", ""),
                affected_areas=result.get("affected_areas", []),
                requester_notes=result.get("requester_notes", ""),
                source_messages=[m.get("id", "") for m in messages],
                requester_id=messages[0].get("user_id", "") if messages else "",
                requester_name=messages[0].get("user_name", "") if messages else "",
            )
        except Exception:
            logger.exception("Failed to parse LLM result into Requirement")
            return None

    # ── Skill: requirement_classify ───────────────────────────────────────

    async def classify_requirement(self, requirement: Requirement) -> Requirement:
        """Re-classify a requirement's type and priority using LLM."""
        prompt = (
            f"## Requirement\n"
            f"Title: {requirement.title}\n"
            f"Description: {requirement.description}\n"
            f"Background: {requirement.background}\n\n"
            f"## Task\nClassify this requirement's type and priority."
        )

        try:
            result = await self.llm.complete_json(
                prompt=prompt,
                system=self._extract_prompt,
                temperature=0.2,
            )
            if "type" in result:
                try:
                    requirement.type = RequirementType(result["type"])
                except ValueError:
                    pass
            if "priority" in result:
                try:
                    requirement.priority = Priority(result["priority"])
                except ValueError:
                    pass
        except Exception:
            logger.exception("Classification failed")

        return requirement

    # ── Skill: priority_assess ────────────────────────────────────────────

    async def assess_priority(
        self, requirement: Requirement
    ) -> dict[str, Any]:
        """Assess priority with detailed reasoning."""
        prompt = (
            f"## Requirement\n"
            f"Title: {requirement.title}\n"
            f"Description: {requirement.description}\n"
            f"Type: {requirement.type.value}\n"
            f"Background: {requirement.background}\n\n"
            f"## Task\nAssess the priority of this requirement."
        )

        try:
            temps = self.config.get("llm", {}).get("temperatures", {})
            return await self.llm.complete_json(
                prompt=prompt,
                system=self._priority_prompt,
                temperature=temps.get("priority_assess", 0.2),
            )
        except Exception:
            logger.exception("Priority assessment failed")
            return {"priority": "P2", "reasoning": "Default priority"}

    # ── Skill: conflict_detect ────────────────────────────────────────────

    async def detect_conflicts(
        self, requirement: Requirement, existing_issues: list[dict]
    ) -> list[dict]:
        """Check if a new requirement conflicts with or duplicates existing ones."""
        if not existing_issues:
            return []

        existing_text = "\n".join(
            f"- #{i['number']}: {i['title']}" for i in existing_issues[:30]
        )

        prompt = (
            f"## New Requirement\n"
            f"Title: {requirement.title}\n"
            f"Description: {requirement.description}\n\n"
            f"## Existing Requirements\n{existing_text}\n\n"
            f"## Task\n"
            f"Check if the new requirement conflicts with or duplicates any existing ones.\n"
            f"Return JSON: {{\"conflicts\": [{{\"issue_number\": N, \"reason\": \"...\", \"type\": \"duplicate|conflict|related\"}}]}}"
        )

        try:
            result = await self.llm.complete_json(prompt=prompt)
            return result.get("conflicts", [])
        except Exception:
            logger.exception("Conflict detection failed")
            return []

    # ── Skill: doc_generate ───────────────────────────────────────────────

    async def generate_doc(self, requirement: Requirement) -> str:
        """Generate a Markdown requirement document."""
        criteria = "\n".join(
            f"- [ ] {c}" for c in requirement.acceptance_criteria
        ) or "- [ ] TBD"

        areas = ", ".join(requirement.affected_areas) or "TBD"

        doc = (
            f"# {requirement.title}\n\n"
            f"**类型**: {requirement.type.value} | "
            f"**优先级**: {requirement.priority.value} | "
            f"**来源**: 运营团队\n\n"
            f"## 背景\n{requirement.background or 'N/A'}\n\n"
            f"## 需求描述\n{requirement.description}\n\n"
            f"## 验收标准\n{criteria}\n\n"
            f"## 影响范围\n{areas}\n\n"
            f"## 备注\n{requirement.requester_notes or 'N/A'}\n"
        )
        return doc

    # ── Skill: analyze dev discussion (Workflow 2) ────────────────────────

    async def analyze_dev_discussion(
        self, messages: list[dict], issue_number: int | None = None
    ) -> dict[str, Any]:
        """Analyze Lark dev discussion and determine what needs ops confirmation."""
        conversation = self._format_messages(messages)

        prompt = (
            f"## Dev Team Discussion\n\n{conversation}\n\n"
            f"## Task\n"
            f"Analyze this developer discussion and determine:\n"
            f"1. Are there questions that need operations team confirmation?\n"
            f"2. What are the key technical notes to archive?\n\n"
            f"Return JSON:\n"
            f'{{"needs_ops_confirmation": true/false, '
            f'"questions": ["question 1", "question 2"], '
            f'"technical_notes": "summary of technical discussion"}}'
        )

        try:
            return await self.llm.complete_json(prompt=prompt, temperature=0.3)
        except Exception:
            logger.exception("Dev discussion analysis failed")
            return {"needs_ops_confirmation": False, "technical_notes": ""}

    # ── Internal ──────────────────────────────────────────────────────────

    @staticmethod
    def _format_messages(messages: list[dict]) -> str:
        lines = []
        for msg in messages:
            name = msg.get("user_name", "Unknown")
            text = msg.get("text", "")
            ts = msg.get("timestamp", "")
            lines.append(f"[{ts}] {name}: {text}")
        return "\n".join(lines)
