"""Lark/Feishu API service - wraps lark-oapi SDK or custom webhook."""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)

from src.core.config import get_settings

logger = logging.getLogger(__name__)


class LarkService:
    """Manages Lark/Feishu messaging and interactive cards."""

    def __init__(self) -> None:
        settings = get_settings()
        self._webhook_url = settings.lark_webhook_url
        self.default_chat_id = settings.lark_group_chat_id

        if not self._webhook_url:
            self.client = lark.Client.builder() \
                .app_id(settings.lark_app_id) \
                .app_secret(settings.lark_app_secret) \
                .log_level(lark.LogLevel.INFO) \
                .build()
        else:
            self.client = None
            logger.info("LarkService using custom webhook URL (single-way push mode)")

    def _post_webhook(self, payload: dict) -> dict[str, Any]:
        """POST payload to custom bot webhook URL."""
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                if result.get("code") == 0 or result.get("StatusCode") == 0:
                    return {"success": True}
                return {"success": False, "error": result.get("msg", "unknown")}
        except Exception as e:
            logger.error("Webhook POST failed: %s", e)
            return {"success": False, "error": str(e)}

    def send_text(self, chat_id: str | None, text: str) -> dict[str, Any]:
        """Send a plain text message to a chat."""
        if self._webhook_url:
            return self._post_webhook({"msg_type": "text", "content": {"text": text}})

        chat_id = chat_id or self.default_chat_id
        body = CreateMessageRequestBody.builder() \
            .receive_id(chat_id) \
            .msg_type("text") \
            .content(json.dumps({"text": text})) \
            .build()

        request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(body) \
            .build()

        response = self.client.im.v1.message.create(request)
        if not response.success():
            logger.error("Lark send_text failed: %s", response.msg)
            return {"success": False, "error": response.msg}

        return {
            "success": True,
            "message_id": response.data.message_id if response.data else None,
        }

    def send_rich_text(self, chat_id: str | None, content: dict) -> dict[str, Any]:
        """Send a rich text (post) message."""
        chat_id = chat_id or self.default_chat_id
        body = CreateMessageRequestBody.builder() \
            .receive_id(chat_id) \
            .msg_type("post") \
            .content(json.dumps(content)) \
            .build()

        request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(body) \
            .build()

        response = self.client.im.v1.message.create(request)
        if not response.success():
            logger.error("Lark send_rich_text failed: %s", response.msg)
            return {"success": False, "error": response.msg}

        return {
            "success": True,
            "message_id": response.data.message_id if response.data else None,
        }

    def send_interactive_card(
        self, chat_id: str | None, card: dict
    ) -> dict[str, Any]:
        """Send an interactive card message."""
        if self._webhook_url:
            # Custom webhook: send as card but buttons won't be interactive
            return self._post_webhook({"msg_type": "interactive", "card": card})

        chat_id = chat_id or self.default_chat_id
        body = CreateMessageRequestBody.builder() \
            .receive_id(chat_id) \
            .msg_type("interactive") \
            .content(json.dumps(card)) \
            .build()

        request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(body) \
            .build()

        response = self.client.im.v1.message.create(request)
        if not response.success():
            logger.error("Lark send_card failed: %s", response.msg)
            return {"success": False, "error": response.msg}

        return {
            "success": True,
            "message_id": response.data.message_id if response.data else None,
        }

    def reply_message(
        self, message_id: str, text: str
    ) -> dict[str, Any]:
        """Reply to a specific message."""
        body = ReplyMessageRequestBody.builder() \
            .msg_type("text") \
            .content(json.dumps({"text": text})) \
            .build()

        request = ReplyMessageRequest.builder() \
            .message_id(message_id) \
            .request_body(body) \
            .build()

        response = self.client.im.v1.message.reply(request)
        if not response.success():
            logger.error("Lark reply failed: %s", response.msg)
            return {"success": False, "error": response.msg}

        return {"success": True}

    def build_requirement_card(
        self,
        title: str,
        description: str,
        priority: str,
        req_type: str,
        issue_number: int | None = None,
        issue_url: str | None = None,
    ) -> dict:
        """Build an interactive card for a new requirement."""
        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**类型**: {req_type} | **优先级**: {priority}",
                },
            },
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": description},
            },
        ]

        if issue_url:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"[GitHub Issue #{issue_number}]({issue_url})",
                },
            })

        elements.append({"tag": "hr"})
        elements.append({
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "接受"},
                    "type": "primary",
                    "value": json.dumps({
                        "action": "accept",
                        "issue_number": issue_number,
                    }),
                },
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "拒绝"},
                    "type": "danger",
                    "value": json.dumps({
                        "action": "reject",
                        "issue_number": issue_number,
                    }),
                },
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "需讨论"},
                    "type": "default",
                    "value": json.dumps({
                        "action": "discuss",
                        "issue_number": issue_number,
                    }),
                },
            ],
        })

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"📋 新需求: {title}"},
                "template": "blue",
            },
            "elements": elements,
        }

    def build_approval_card(
        self,
        title: str,
        questions: list[str],
        issue_number: int,
    ) -> dict:
        """Build an approval card for Lark admin."""
        question_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"⚠️ 待审批: {title}"},
                "template": "orange",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**需运营确认的问题列表**\n\n{question_text}",
                    },
                },
                {"tag": "hr"},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "确认推送"},
                            "type": "primary",
                            "value": json.dumps({
                                "action": "approve",
                                "issue_number": issue_number,
                            }),
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "暂缓"},
                            "type": "default",
                            "value": json.dumps({
                                "action": "reject",
                                "issue_number": issue_number,
                            }),
                        },
                    ],
                },
            ],
        }
