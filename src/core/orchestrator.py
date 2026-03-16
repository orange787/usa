"""Orchestrator Agent - Central coordinator for all agents."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.core.config import get_whitelist, get_app_config
from src.core.models import (
    Event,
    EventType,
    ApprovalAction,
    MessageSource,
    RequirementStatus,
)
from src.core.event_bus import EventBus

if TYPE_CHECKING:
    from src.agents.tg_listener import TGListenerAgent
    from src.agents.requirement_analyst import RequirementAnalystAgent
    from src.agents.github_manager import GitHubManagerAgent
    from src.agents.lark_dispatcher import LarkDispatcherAgent
    from src.agents.status_sync import StatusSyncAgent

logger = logging.getLogger(__name__)


class Orchestrator:
    """Coordinates all agents and manages workflow routing."""

    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus
        self.whitelist = get_whitelist()
        self.config = get_app_config()

        # Agent references (set during init)
        self.tg_listener: TGListenerAgent | None = None
        self.analyst: RequirementAnalystAgent | None = None
        self.github_manager: GitHubManagerAgent | None = None
        self.lark_dispatcher: LarkDispatcherAgent | None = None
        self.status_sync: StatusSyncAgent | None = None

    def register_agents(
        self,
        tg_listener: TGListenerAgent,
        analyst: RequirementAnalystAgent,
        github_manager: GitHubManagerAgent,
        lark_dispatcher: LarkDispatcherAgent,
        status_sync: StatusSyncAgent,
    ) -> None:
        self.tg_listener = tg_listener
        self.analyst = analyst
        self.github_manager = github_manager
        self.lark_dispatcher = lark_dispatcher
        self.status_sync = status_sync

    async def setup(self) -> None:
        """Subscribe to events and wire up the workflow."""
        bus = self.event_bus

        # Workflow 1: TG message → Requirement extraction
        bus.subscribe(EventType.TG_KEYWORD_DETECTED, self._handle_keyword_detected)
        bus.subscribe(EventType.TG_COMMAND_RECEIVED, self._handle_tg_command)

        # Workflow 1 cont: Requirement extracted → TG approval
        bus.subscribe(EventType.REQ_EXTRACTED, self._handle_requirement_extracted)

        # Workflow 1 cont: TG approval response → GitHub issue
        bus.subscribe(EventType.TG_APPROVAL_RESPONSE, self._handle_tg_approval)

        # Workflow 1 cont: GitHub issue created → Lark push
        bus.subscribe(EventType.GH_ISSUE_CREATED, self._handle_issue_created)

        # Workflow 2: Lark message → analyze & sync
        bus.subscribe(EventType.LARK_MESSAGE_RECEIVED, self._handle_lark_message)
        bus.subscribe(EventType.LARK_CARD_ACTION, self._handle_lark_card_action)
        bus.subscribe(EventType.LARK_APPROVAL_RESPONSE, self._handle_lark_approval)

        # Workflow 3: Status sync
        bus.subscribe(EventType.GH_STATUS_CHANGED, self._handle_status_changed)
        bus.subscribe(EventType.SYNC_PROGRESS_UPDATE, self._handle_progress_update)

        # Error handling
        bus.subscribe(EventType.SYSTEM_ERROR, self._handle_error)

        logger.info("Orchestrator setup complete")

    # ── Workflow 1: Requirement Collection ────────────────────────────────

    async def _handle_keyword_detected(self, event: Event) -> None:
        """Keyword detected in TG → extract requirement."""
        if not self.analyst:
            return
        messages = event.data.get("messages", [])
        requirement = await self.analyst.extract_requirement(messages)
        if requirement:
            await self.event_bus.publish(Event(
                type=EventType.REQ_EXTRACTED,
                data={
                    "requirement": requirement.model_dump(),
                    "chat_id": event.data.get("chat_id"),
                },
                source="orchestrator",
            ))

    async def _handle_tg_command(self, event: Event) -> None:
        """Handle TG bot commands."""
        command = event.data.get("command", "")
        if command == "/submit":
            await self._handle_keyword_detected(event)
        elif command == "/status" and self.github_manager:
            issues = await self.github_manager.query_issues(state="open")
            if self.tg_listener:
                await self.tg_listener.send_status_list(
                    event.data.get("chat_id"), issues
                )
        elif command == "/list" and self.github_manager:
            issues = await self.github_manager.query_issues()
            if self.tg_listener:
                await self.tg_listener.send_issue_list(
                    event.data.get("chat_id"), issues
                )

    async def _handle_requirement_extracted(self, event: Event) -> None:
        """Requirement extracted → send approval card to TG admin."""
        if not self.tg_listener:
            return
        requirement_data = event.data.get("requirement", {})
        chat_id = event.data.get("chat_id")
        await self.tg_listener.send_approval_card(
            requirement_data, chat_id
        )

    async def _handle_tg_approval(self, event: Event) -> None:
        """TG admin approved/rejected requirement."""
        action = event.data.get("action")
        user_id = event.data.get("user_id")

        if not self._is_tg_admin(user_id):
            logger.warning("Non-admin TG user %s tried to approve", user_id)
            return

        requirement_data = event.data.get("requirement", {})

        if action == ApprovalAction.APPROVE.value:
            # Create GitHub issue
            if self.github_manager:
                issue = await self.github_manager.create_issue(requirement_data)
                await self.event_bus.publish(Event(
                    type=EventType.GH_ISSUE_CREATED,
                    data={
                        "requirement": requirement_data,
                        "issue_number": issue.get("number"),
                        "issue_url": issue.get("url"),
                    },
                    source="orchestrator",
                ))
        elif action == ApprovalAction.REJECT.value:
            await self.event_bus.publish(Event(
                type=EventType.REQ_REJECTED,
                data={"requirement": requirement_data},
                source="orchestrator",
            ))

    async def _handle_issue_created(self, event: Event) -> None:
        """GitHub issue created → push to Lark."""
        if not self.lark_dispatcher:
            return
        await self.lark_dispatcher.push_requirement(
            event.data.get("requirement", {}),
            event.data.get("issue_number"),
            event.data.get("issue_url"),
        )

    # ── Workflow 2: Lark Discussion → Sync ────────────────────────────────

    async def _handle_lark_message(self, event: Event) -> None:
        """Lark message received → analyze for questions."""
        if not self.analyst:
            return
        messages = event.data.get("messages", [])
        issue_number = event.data.get("issue_number")
        analysis = await self.analyst.analyze_dev_discussion(messages, issue_number)

        if analysis.get("needs_ops_confirmation"):
            # Send question list to Lark admin for approval
            if self.lark_dispatcher:
                await self.lark_dispatcher.send_admin_approval(
                    analysis.get("questions", []),
                    issue_number,
                )
        elif analysis.get("technical_notes"):
            # Archive technical discussion to GitHub
            if self.github_manager and issue_number:
                await self.github_manager.add_comment(
                    issue_number, analysis["technical_notes"]
                )

    async def _handle_lark_card_action(self, event: Event) -> None:
        """Handle Lark interactive card button clicks."""
        action_id = event.data.get("action_id")
        issue_number = event.data.get("issue_number")

        if action_id == "accept" and self.github_manager and issue_number:
            await self.github_manager.update_status(issue_number, "status/in-progress")
        elif action_id == "reject" and self.github_manager and issue_number:
            await self.github_manager.add_comment(
                issue_number,
                f"开发团队拒绝: {event.data.get('reason', '未说明原因')}",
            )
        elif action_id == "discuss":
            pass  # Discussion continues in Lark thread

    async def _handle_lark_approval(self, event: Event) -> None:
        """Lark admin approved question list → push to TG."""
        user_id = event.data.get("user_id")
        if not self._is_lark_admin(user_id):
            logger.warning("Non-admin Lark user %s tried to approve", user_id)
            return

        action = event.data.get("action")
        if action == ApprovalAction.APPROVE.value:
            questions = event.data.get("questions", [])
            issue_number = event.data.get("issue_number")

            # Archive to GitHub
            if self.github_manager and issue_number:
                await self.github_manager.add_comment(
                    issue_number,
                    "## 待运营确认的问题\n" + "\n".join(
                        f"- {q}" for q in questions
                    ),
                )

            # Push to TG
            if self.tg_listener:
                await self.tg_listener.send_question_list(questions, issue_number)

    # ── Workflow 3: Status Sync ───────────────────────────────────────────

    async def _handle_status_changed(self, event: Event) -> None:
        """GitHub status changed → notify both TG and Lark."""
        if self.status_sync:
            await self.status_sync.sync_status_change(event.data)

    async def _handle_progress_update(self, event: Event) -> None:
        """Progress update → notify TG ops team."""
        if self.tg_listener:
            await self.tg_listener.send_progress_update(event.data)

    # ── Error Handling ────────────────────────────────────────────────────

    async def _handle_error(self, event: Event) -> None:
        logger.error("System error: %s", event.data)

    # ── Whitelist Checks ──────────────────────────────────────────────────

    def _is_tg_admin(self, user_id: int | str) -> bool:
        admin_ids = self.whitelist.get("telegram", {}).get("admin_ids", [])
        return int(user_id) in admin_ids

    def _is_lark_admin(self, user_id: str) -> bool:
        admin_ids = self.whitelist.get("lark", {}).get("admin_ids", [])
        return user_id in admin_ids
