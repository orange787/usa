"""Agent 5: Status Sync Agent - Bidirectional status synchronization."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from src.core.config import get_app_config, load_prompt
from src.core.event_bus import EventBus
from src.core.models import Event, EventType, DailyDigest
from src.services.llm.base import BaseLLM

logger = logging.getLogger(__name__)


class StatusSyncAgent:
    """Keeps Telegram, GitHub, and Lark in sync."""

    def __init__(
        self,
        event_bus: EventBus,
        llm: BaseLLM,
    ) -> None:
        self.event_bus = event_bus
        self.llm = llm
        self.config = get_app_config()

        # References set by orchestrator
        self.tg_listener = None
        self.lark_dispatcher = None
        self.github_manager = None

    def set_agents(self, tg_listener, lark_dispatcher, github_manager) -> None:
        self.tg_listener = tg_listener
        self.lark_dispatcher = lark_dispatcher
        self.github_manager = github_manager

    # ── Skill: bidirectional_sync ─────────────────────────────────────────

    async def sync_status_change(self, data: dict) -> None:
        """Sync a GitHub status change to both TG and Lark."""
        issue_number = data.get("issue_number")
        title = data.get("title", "")
        old_status = data.get("old_status", "")
        new_status = data.get("new_status", "")

        # Notify TG
        if self.tg_listener:
            await self.tg_listener.send_progress_update(data)

        # Notify Lark
        if self.lark_dispatcher:
            await self.lark_dispatcher.send_status_update(
                issue_number, title, old_status, new_status
            )

        logger.info(
            "Synced status change for #%s: %s → %s",
            issue_number, old_status, new_status,
        )

    # ── Skill: progress_broadcast ─────────────────────────────────────────

    async def broadcast_progress(self, data: dict) -> None:
        """Broadcast a progress update to TG ops team."""
        await self.event_bus.publish(Event(
            type=EventType.SYNC_PROGRESS_UPDATE,
            data=data,
            source="status_sync",
        ))

    # ── Skill: daily_digest ───────────────────────────────────────────────

    async def generate_daily_digest(self) -> str:
        """Generate and distribute daily digest."""
        if not self.github_manager:
            return ""

        report = await self.github_manager.generate_report()
        issues = await self.github_manager.query_issues(state="open")

        # Build digest
        now = datetime.utcnow()
        escalation_hours = self.config.get("scheduling", {}).get(
            "escalation_timeout_hours", 48
        )

        # Find overdue items
        overdue = []
        pending_confirmation = []
        recent_changes = []

        for issue in issues:
            labels = issue.get("labels", [])
            updated = datetime.fromisoformat(issue["updated_at"])
            age_hours = (now - updated).total_seconds() / 3600

            if age_hours > escalation_hours and "status/todo" in labels:
                overdue.append(f"#{issue['number']} {issue['title']} ({int(age_hours)}h 未处理)")

            if "approval/pending" in labels:
                pending_confirmation.append(f"#{issue['number']} {issue['title']}")

        digest_text = (
            f"📊 需求日报 - {now.strftime('%Y-%m-%d')}\n\n"
            f"## 总览\n"
            f"- 总计: {report['total']}\n"
            f"- 待处理: {report['by_status'].get('todo', 0)}\n"
            f"- 进行中: {report['by_status'].get('in-progress', 0)}\n"
            f"- 验收中: {report['by_status'].get('review', 0)}\n"
            f"- 已完成: {report['by_status'].get('done', 0)}\n\n"
        )

        if overdue:
            digest_text += "## ⚠️ 超时未处理\n"
            digest_text += "\n".join(f"- {item}" for item in overdue)
            digest_text += "\n\n"

        if pending_confirmation:
            digest_text += "## ❓ 待确认\n"
            digest_text += "\n".join(f"- {item}" for item in pending_confirmation)
            digest_text += "\n\n"

        # Distribute
        if self.tg_listener and self.tg_listener.bot:
            from src.core.config import get_whitelist
            whitelist = get_whitelist()
            tg_chat = whitelist.get("telegram", {}).get("allowed_groups", [None])[0]
            if tg_chat:
                await self.tg_listener.bot.send_message(
                    chat_id=int(tg_chat),
                    text=digest_text,
                )

        if self.lark_dispatcher:
            await self.lark_dispatcher.send_daily_digest(digest_text)

        logger.info("Daily digest generated and distributed")
        return digest_text

    # ── Skill: escalation ─────────────────────────────────────────────────

    async def check_escalations(self) -> list[dict]:
        """Check for overdue requirements and trigger escalation."""
        if not self.github_manager:
            return []

        issues = await self.github_manager.query_issues(
            state="open", labels=["status/todo"]
        )

        escalation_hours = self.config.get("scheduling", {}).get(
            "escalation_timeout_hours", 48
        )
        now = datetime.utcnow()
        escalated = []

        for issue in issues:
            updated = datetime.fromisoformat(issue["updated_at"])
            age_hours = (now - updated).total_seconds() / 3600

            if age_hours > escalation_hours:
                escalated.append(issue)

                await self.event_bus.publish(Event(
                    type=EventType.SYNC_ESCALATION,
                    data={
                        "issue_number": issue["number"],
                        "title": issue["title"],
                        "hours_overdue": int(age_hours),
                    },
                    source="status_sync",
                ))

                # Notify Lark
                if self.lark_dispatcher:
                    await self.lark_dispatcher.send_reminder(
                        issue["number"],
                        issue["title"],
                        f"此需求已 {int(age_hours)} 小时未处理，请及时响应。",
                    )

        return escalated

    # ── Skill: changelog_generate ─────────────────────────────────────────

    async def generate_changelog(self, milestone: str | None = None) -> str:
        """Generate a changelog from completed issues."""
        if not self.github_manager:
            return ""

        labels = ["status/done"]
        issues = await self.github_manager.query_issues(
            state="closed", labels=labels
        )

        if not issues:
            return "No completed items found."

        # Group by type
        by_type: dict[str, list] = {}
        for issue in issues:
            issue_labels = issue.get("labels", [])
            req_type = "other"
            for label in issue_labels:
                if label.startswith("type/"):
                    req_type = label.replace("type/", "")
                    break
            by_type.setdefault(req_type, []).append(issue)

        type_names = {
            "feature": "✨ 新功能",
            "bug": "🐛 Bug 修复",
            "data": "📊 数据需求",
            "event": "🎮 活动需求",
            "optimization": "⚡ 优化改进",
            "other": "📝 其他",
        }

        lines = [f"# 变更日志\n"]
        for typ, typ_issues in by_type.items():
            lines.append(f"\n## {type_names.get(typ, typ)}\n")
            for issue in typ_issues:
                lines.append(f"- #{issue['number']} {issue['title']}")

        return "\n".join(lines)
