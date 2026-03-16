"""Agent 1: TG Listener Agent - Telegram message collection and interaction."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from src.core.config import get_app_config, get_whitelist
from src.core.event_bus import EventBus
from src.core.models import (
    ChatMessage,
    Event,
    EventType,
    MessageSource,
)

logger = logging.getLogger(__name__)


class TGListenerAgent:
    """Listens to Telegram group messages and manages user interactions."""

    def __init__(self, event_bus: EventBus, bot: Any = None) -> None:
        self.event_bus = event_bus
        self.bot = bot  # telegram.Bot instance, set during init
        self.config = get_app_config()
        self.whitelist = get_whitelist()
        self._keywords = self.config.get("telegram", {}).get("trigger_keywords", [])
        self._message_buffer: dict[str, list[ChatMessage]] = {}

    # ── Skill: message_capture ────────────────────────────────────────────

    async def handle_message(self, update: Any, context: Any) -> None:
        """Capture incoming group messages and check for keywords."""
        message = update.effective_message
        if not message or not message.text:
            return

        chat_msg = ChatMessage(
            id=str(message.message_id),
            source=MessageSource.TELEGRAM,
            chat_id=str(message.chat_id),
            user_id=str(message.from_user.id) if message.from_user else "",
            user_name=message.from_user.full_name if message.from_user else "Unknown",
            text=message.text,
            reply_to_id=(
                str(message.reply_to_message.message_id)
                if message.reply_to_message
                else None
            ),
            thread_id=str(message.message_thread_id) if message.is_topic_message else None,
        )

        # Buffer message for thread tracking
        thread_key = chat_msg.thread_id or chat_msg.chat_id
        if thread_key not in self._message_buffer:
            self._message_buffer[thread_key] = []
        self._message_buffer[thread_key].append(chat_msg)

        # Keep buffer reasonable
        if len(self._message_buffer[thread_key]) > 50:
            self._message_buffer[thread_key] = self._message_buffer[thread_key][-30:]

        # Skill: keyword_alert
        if self._check_keywords(message.text):
            recent = self._message_buffer[thread_key][-10:]
            await self.event_bus.publish(Event(
                type=EventType.TG_KEYWORD_DETECTED,
                data={
                    "messages": [m.model_dump() for m in recent],
                    "chat_id": str(message.chat_id),
                    "trigger_message": chat_msg.model_dump(),
                },
                source="tg_listener",
            ))

    # ── Skill: user_interaction (Bot commands) ────────────────────────────

    async def handle_submit(self, update: Any, context: Any) -> None:
        """Handle /submit command - manually trigger requirement extraction."""
        message = update.effective_message
        if not message:
            return

        chat_id = str(message.chat_id)
        thread_key = (
            str(message.message_thread_id)
            if message.is_topic_message
            else chat_id
        )

        # Get recent messages from buffer
        recent = self._message_buffer.get(thread_key, [])[-15:]
        if not recent:
            await message.reply_text("没有找到最近的聊天记录，请先讨论需求后再提交。")
            return

        await message.reply_text("📝 正在分析需求，请稍候...")

        await self.event_bus.publish(Event(
            type=EventType.TG_COMMAND_RECEIVED,
            data={
                "command": "/submit",
                "messages": [m.model_dump() for m in recent],
                "chat_id": chat_id,
                "user_id": str(message.from_user.id) if message.from_user else "",
            },
            source="tg_listener",
        ))

    async def handle_status(self, update: Any, context: Any) -> None:
        """Handle /status command."""
        message = update.effective_message
        if not message:
            return
        await self.event_bus.publish(Event(
            type=EventType.TG_COMMAND_RECEIVED,
            data={
                "command": "/status",
                "chat_id": str(message.chat_id),
            },
            source="tg_listener",
        ))

    async def handle_list(self, update: Any, context: Any) -> None:
        """Handle /list command."""
        message = update.effective_message
        if not message:
            return
        await self.event_bus.publish(Event(
            type=EventType.TG_COMMAND_RECEIVED,
            data={
                "command": "/list",
                "chat_id": str(message.chat_id),
            },
            source="tg_listener",
        ))

    async def handle_help(self, update: Any, context: Any) -> None:
        """Handle /help command."""
        message = update.effective_message
        if not message:
            return
        help_text = (
            "🤖 *需求收集 Bot 帮助*\n\n"
            "/submit - 提交需求（基于最近的聊天记录）\n"
            "/status - 查看进行中的需求状态\n"
            "/list - 查看所有需求列表\n"
            "/help - 显示此帮助信息\n\n"
            '💡 *自动触发*: 在聊天中提到"需求"、"bug"、"紧急"等关键词时，'
            "Bot 会自动识别并提示是否提交需求。"
        )
        await message.reply_text(help_text, parse_mode="Markdown")

    # ── Skill: admin_approval ─────────────────────────────────────────────

    async def send_approval_card(
        self, requirement_data: dict, chat_id: str | None = None
    ) -> None:
        """Send an approval card to TG group for admin review."""
        if not self.bot:
            logger.warning("TG bot not initialized, can't send approval card")
            return

        target_chat = chat_id or str(
            self.whitelist.get("telegram", {}).get("allowed_groups", [None])[0]
        )

        title = requirement_data.get("title", "未命名需求")
        desc = requirement_data.get("description", "")
        priority = requirement_data.get("priority", "P2")
        req_type = requirement_data.get("type", "feature")
        criteria = requirement_data.get("acceptance_criteria", [])

        criteria_text = ""
        if criteria:
            criteria_text = "\n*验收标准:*\n" + "\n".join(f"  • {c}" for c in criteria)

        text = (
            f"📋 *新需求待审批*\n\n"
            f"*标题:* {title}\n"
            f"*类型:* {req_type} | *优先级:* {priority}\n\n"
            f"*描述:*\n{desc}\n"
            f"{criteria_text}\n\n"
            f"管理员请回复:\n"
            f"  ✅ 回复 `approve` 通过\n"
            f"  ❌ 回复 `reject` 驳回\n"
            f"  ✏️ 回复 `modify: 修改意见` 修改后通过"
        )

        msg = await self.bot.send_message(
            chat_id=int(target_chat),
            text=text,
            parse_mode="Markdown",
        )

        # Store requirement data keyed by message ID for later retrieval
        self._pending_approvals = getattr(self, "_pending_approvals", {})
        self._pending_approvals[str(msg.message_id)] = requirement_data

    async def handle_approval_reply(self, update: Any, context: Any) -> None:
        """Handle admin's reply to an approval card."""
        message = update.effective_message
        if not message or not message.reply_to_message:
            return

        user_id = str(message.from_user.id) if message.from_user else ""
        reply_to_id = str(message.reply_to_message.message_id)

        pending = getattr(self, "_pending_approvals", {})
        requirement_data = pending.get(reply_to_id)
        if not requirement_data:
            return

        text = message.text.strip().lower()
        if text.startswith("approve"):
            action = "approve"
        elif text.startswith("reject"):
            action = "reject"
        elif text.startswith("modify:"):
            action = "modify"
            requirement_data["requester_notes"] = text[7:].strip()
        else:
            return

        await self.event_bus.publish(Event(
            type=EventType.TG_APPROVAL_RESPONSE,
            data={
                "action": action,
                "user_id": user_id,
                "requirement": requirement_data,
                "chat_id": str(message.chat_id),
            },
            source="tg_listener",
        ))

        # Clean up
        del pending[reply_to_id]

        status_emoji = {"approve": "✅", "reject": "❌", "modify": "✏️"}
        await message.reply_text(
            f"{status_emoji.get(action, '📝')} 需求已{action}",
        )

    # ── Skill: send messages back to TG ───────────────────────────────────

    async def send_status_list(
        self, chat_id: str | None, issues: list[dict]
    ) -> None:
        """Send a formatted status list to TG."""
        if not self.bot or not chat_id:
            return

        if not issues:
            await self.bot.send_message(chat_id=int(chat_id), text="📭 当前没有进行中的需求")
            return

        lines = ["📊 *进行中的需求:*\n"]
        for issue in issues[:20]:
            labels = issue.get("labels", [])
            priority = next((l for l in labels if l.startswith("priority/")), "")
            status = next((l for l in labels if l.startswith("status/")), "")
            lines.append(
                f"• #{issue['number']} {issue['title']}\n"
                f"  {priority} | {status}"
            )
        await self.bot.send_message(
            chat_id=int(chat_id),
            text="\n".join(lines),
            parse_mode="Markdown",
        )

    async def send_issue_list(
        self, chat_id: str | None, issues: list[dict]
    ) -> None:
        """Send a formatted issue list to TG."""
        if not self.bot or not chat_id:
            return
        if not issues:
            await self.bot.send_message(chat_id=int(chat_id), text="📭 没有需求记录")
            return

        lines = ["📋 *需求列表:*\n"]
        for issue in issues[:30]:
            state = "🟢" if issue["state"] == "open" else "✅"
            lines.append(f"{state} #{issue['number']} {issue['title']}")
        await self.bot.send_message(
            chat_id=int(chat_id),
            text="\n".join(lines),
            parse_mode="Markdown",
        )

    async def send_question_list(
        self, questions: list[str], issue_number: int | None
    ) -> None:
        """Send question list from dev team to TG ops group."""
        if not self.bot:
            return

        target_chat = self.whitelist.get("telegram", {}).get("allowed_groups", [None])[0]
        if not target_chat:
            return

        q_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        text = (
            f"❓ *开发团队有以下问题需确认*"
            f"{f' (Issue #{issue_number})' if issue_number else ''}\n\n"
            f"{q_text}\n\n"
            f"请在此回复您的意见。"
        )
        await self.bot.send_message(
            chat_id=int(target_chat),
            text=text,
            parse_mode="Markdown",
        )

    async def send_progress_update(self, data: dict) -> None:
        """Send progress update to TG ops group."""
        if not self.bot:
            return

        target_chat = self.whitelist.get("telegram", {}).get("allowed_groups", [None])[0]
        if not target_chat:
            return

        issue_number = data.get("issue_number")
        title = data.get("title", "")
        old_status = data.get("old_status", "")
        new_status = data.get("new_status", "")

        text = (
            f"🔄 *需求进度更新*\n\n"
            f"#{issue_number} {title}\n"
            f"状态: {old_status} → {new_status}"
        )
        await self.bot.send_message(
            chat_id=int(target_chat),
            text=text,
            parse_mode="Markdown",
        )

    # ── Internal ──────────────────────────────────────────────────────────

    def _check_keywords(self, text: str) -> bool:
        return any(kw in text for kw in self._keywords)
