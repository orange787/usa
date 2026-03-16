"""Agent 4: Lark Dispatcher Agent - Feishu/Lark integration."""

from __future__ import annotations

import json
import logging
from typing import Any

from src.core.config import get_whitelist
from src.core.event_bus import EventBus
from src.core.models import Event, EventType
from src.services.lark_service import LarkService

logger = logging.getLogger(__name__)


class LarkDispatcherAgent:
    """Dispatches requirements to Lark and collects dev feedback."""

    def __init__(
        self, event_bus: EventBus, lark_service: LarkService
    ) -> None:
        self.event_bus = event_bus
        self.lark = lark_service
        self.whitelist = get_whitelist()
        # Track issue_number → lark_message_id for threading
        self._issue_messages: dict[int, str] = {}

    # ── Skill: requirement_push ───────────────────────────────────────────

    async def push_requirement(
        self,
        requirement_data: dict,
        issue_number: int | None = None,
        issue_url: str | None = None,
        chat_id: str | None = None,
    ) -> None:
        """Push a new requirement to Lark as an interactive card."""
        card = self.lark.build_requirement_card(
            title=requirement_data.get("title", "未命名需求"),
            description=requirement_data.get("description", ""),
            priority=requirement_data.get("priority", "P2"),
            req_type=requirement_data.get("type", "feature"),
            issue_number=issue_number,
            issue_url=issue_url,
        )

        result = self.lark.send_interactive_card(chat_id, card)
        if result.get("success") and result.get("message_id") and issue_number:
            self._issue_messages[issue_number] = result["message_id"]

        logger.info(
            "Pushed requirement to Lark: %s (issue #%s)",
            requirement_data.get("title"),
            issue_number,
        )

    # ── Skill: assignee_notify ────────────────────────────────────────────

    async def notify_assignee(
        self, user_id: str, message: str, chat_id: str | None = None
    ) -> None:
        """Send a notification mentioning a specific developer."""
        text = f"<at user_id=\"{user_id}\"></at> {message}"
        self.lark.send_text(chat_id, text)

    # ── Skill: progress_collect (via card action handler) ─────────────────

    async def handle_card_action(self, action_data: dict) -> None:
        """Process Lark interactive card button clicks."""
        value = action_data.get("value", "{}")
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = {}

        action = value.get("action")
        issue_number = value.get("issue_number")
        user_id = action_data.get("user_id", "")

        await self.event_bus.publish(Event(
            type=EventType.LARK_CARD_ACTION,
            data={
                "action_id": action,
                "issue_number": issue_number,
                "user_id": user_id,
                "reason": action_data.get("reason", ""),
            },
            source="lark_dispatcher",
        ))

    # ── Skill: admin_approval ─────────────────────────────────────────────

    async def send_admin_approval(
        self,
        questions: list[str],
        issue_number: int | None = None,
        chat_id: str | None = None,
    ) -> None:
        """Send question list to Lark admin for approval before pushing to TG."""
        card = self.lark.build_approval_card(
            title=f"Issue #{issue_number}" if issue_number else "需求讨论",
            questions=questions,
            issue_number=issue_number or 0,
        )
        self.lark.send_interactive_card(chat_id, card)
        logger.info("Sent approval card to Lark admin for issue #%s", issue_number)

    async def handle_admin_approval(self, action_data: dict) -> None:
        """Handle Lark admin's approval/rejection of question list."""
        value = action_data.get("value", "{}")
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = {}

        action = value.get("action")
        issue_number = value.get("issue_number")
        user_id = action_data.get("user_id", "")

        await self.event_bus.publish(Event(
            type=EventType.LARK_APPROVAL_RESPONSE,
            data={
                "action": action,
                "issue_number": issue_number,
                "user_id": user_id,
                "questions": action_data.get("questions", []),
            },
            source="lark_dispatcher",
        ))

    # ── Skill: question_list_push ─────────────────────────────────────────

    async def push_question_list(
        self,
        questions: list[str],
        issue_number: int | None = None,
        chat_id: str | None = None,
    ) -> None:
        """Push question list to Lark group for developer discussion."""
        q_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        text = (
            f"❓ 以下问题需要讨论确认"
            f"{f' (Issue #{issue_number})' if issue_number else ''}:\n\n"
            f"{q_text}"
        )
        self.lark.send_text(chat_id, text)

    # ── Skill: schedule_remind ────────────────────────────────────────────

    async def send_reminder(
        self,
        issue_number: int,
        title: str,
        message: str,
        chat_id: str | None = None,
    ) -> None:
        """Send a reminder about an unresponded requirement."""
        text = f"⏰ 提醒: Issue #{issue_number} - {title}\n{message}"
        self.lark.send_text(chat_id, text)

    # ── Skill: dev_feedback_parse ─────────────────────────────────────────

    async def handle_dev_message(self, message_data: dict) -> None:
        """Handle a developer's message in Lark, forward to event bus."""
        await self.event_bus.publish(Event(
            type=EventType.LARK_MESSAGE_RECEIVED,
            data=message_data,
            source="lark_dispatcher",
        ))

    # ── Send status update to Lark ────────────────────────────────────────

    async def send_status_update(
        self,
        issue_number: int,
        title: str,
        old_status: str,
        new_status: str,
        chat_id: str | None = None,
    ) -> None:
        """Send status change notification to Lark group."""
        text = (
            f"🔄 需求状态更新\n"
            f"#{issue_number} {title}\n"
            f"状态: {old_status} → {new_status}"
        )
        self.lark.send_text(chat_id, text)

    async def send_daily_digest(
        self, digest_text: str, chat_id: str | None = None
    ) -> None:
        """Send daily digest to Lark group."""
        self.lark.send_text(chat_id, digest_text)
