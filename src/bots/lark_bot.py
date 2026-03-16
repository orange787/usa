"""Lark Bot entry point - webhook server for Lark events."""

from __future__ import annotations

import json
import logging
from typing import Any

from aiohttp import web

import lark_oapi as lark
from lark_oapi.core.model import RawRequest, RawResponse

from src.core.config import get_settings
from src.agents.lark_dispatcher import LarkDispatcherAgent

logger = logging.getLogger(__name__)


def _build_raw_request(path: str, headers: dict, body: bytes) -> RawRequest:
    req = RawRequest()
    req.uri = path
    req.body = body
    req.headers = headers
    return req


class LarkBotServer:
    """HTTP server that handles Lark webhook events."""

    def __init__(self, lark_dispatcher: LarkDispatcherAgent) -> None:
        self.dispatcher = lark_dispatcher
        settings = get_settings()

        # Build Lark event dispatcher
        self._event_handler = (
            lark.EventDispatcherHandler.builder(
                settings.lark_verification_token,
                settings.lark_encrypt_key,
            )
            .register_p2_im_message_receive_v1(self._on_message)
            .build()
        )

        # Card action handler
        self._card_handler = (
            lark.CardActionHandler.builder(
                settings.lark_verification_token,
                settings.lark_encrypt_key,
            )
            .register(self._on_card_action)
            .build()
        )

    async def _on_message_raw(self, data: dict) -> None:
        """Handle incoming Lark messages from raw JSON."""
        try:
            event = data.get("event", {})
            msg = event.get("message", {})
            sender = event.get("sender", {})

            content = json.loads(msg.get("content", "{}"))
            text = content.get("text", "")

            message_data = {
                "message_id": msg.get("message_id", ""),
                "chat_id": msg.get("chat_id", ""),
                "user_id": sender.get("sender_id", {}).get("user_id", ""),
                "text": text,
                "msg_type": msg.get("message_type", ""),
            }

            await self.dispatcher.handle_dev_message(message_data)
        except Exception:
            logger.exception("Error handling raw Lark message")

    async def _on_message(self, data: Any) -> None:
        """Handle incoming Lark messages."""
        try:
            event = data.event
            msg = event.message
            sender = event.sender

            content = json.loads(msg.content) if msg.content else {}
            text = content.get("text", "")

            message_data = {
                "message_id": msg.message_id,
                "chat_id": msg.chat_id,
                "user_id": sender.sender_id.user_id if sender.sender_id else "",
                "text": text,
                "msg_type": msg.message_type,
            }

            await self.dispatcher.handle_dev_message(message_data)
        except Exception:
            logger.exception("Error handling Lark message")

    def _on_card_action(self, data: Any) -> Any:
        """Handle Lark card button clicks."""
        try:
            action = data.event.action
            user_id = ""
            if data.event.operator and data.event.operator.user_id:
                user_id = data.event.operator.user_id

            import asyncio
            asyncio.create_task(
                self.dispatcher.handle_card_action({
                    "value": action.value if action else "{}",
                    "user_id": user_id,
                })
            )
        except Exception:
            logger.exception("Error handling Lark card action")

        return {}

    def create_web_app(self) -> web.Application:
        """Create an aiohttp web application for Lark webhooks."""
        app = web.Application()

        async def handle_event(request: web.Request) -> web.Response:
            body = await request.read()
            try:
                data = json.loads(body)
                # URL verification challenge
                if data.get("type") == "url_verification":
                    return web.json_response({"challenge": data.get("challenge", "")})
                # Handle message event directly
                event_type = data.get("header", {}).get("event_type", "")
                if event_type == "im.message.receive_v1":
                    await self._on_message_raw(data)
                return web.json_response({"code": 0})
            except Exception:
                logger.exception("Error handling Lark event")
                return web.json_response({"code": 0})

        async def handle_card(request: web.Request) -> web.Response:
            body = await request.read()
            try:
                data = json.loads(body)
                if "challenge" in data:
                    return web.json_response({"challenge": data["challenge"]})
                if data.get("type") == "url_verification":
                    return web.json_response({"challenge": data.get("challenge", "")})

                # New card.action.trigger format (schema 2.0)
                event = data.get("event", {})
                if event:
                    action = event.get("action", {})
                    operator = event.get("operator", {})
                    action_data = {
                        "value": action.get("value", {}),
                        "user_id": operator.get("user_id", ""),
                    }
                else:
                    # Legacy format
                    action_data = data

                logger.info("Card action_data: %s", action_data)
                await self.dispatcher.handle_card_action(action_data)
                return web.json_response({
                    "toast": {"type": "success", "content": "操作成功"}
                })
            except Exception as e:
                logger.exception("Card action error: %s | body: %s", e, body)
                return web.json_response({
                    "toast": {"type": "error", "content": "操作失败，请重试"}
                })

        async def health(request: web.Request) -> web.Response:
            return web.json_response({"status": "ok"})

        app.router.add_post("/lark/event", handle_event)
        app.router.add_post("/lark/card", handle_card)
        app.router.add_get("/health", health)

        return app


async def start_lark_server(
    lark_dispatcher: LarkDispatcherAgent,
    host: str = "0.0.0.0",
    port: int = 8443,
) -> web.AppRunner:
    """Start the Lark webhook server."""
    server = LarkBotServer(lark_dispatcher)
    app = server.create_web_app()

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()

    logger.info("Lark webhook server started on %s:%d", host, port)
    return runner
