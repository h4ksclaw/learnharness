"""Telegram channel adapter.

Uses the Telegram Bot API (long polling). No external deps — pure httpx.

Config (from agent.channels["telegram"]):
    {
        "token": "123456:ABC-DEF...",
        "allowed_users": ["@mattf"],          # restrict who can talk (empty = all)
        "blocked_users": ["@spammer"],        # always blocked
        "allowed_chat_ids": [-1001234567890], # optional channel whitelist
        "allow_dms": true,                    # respond to DMs (private chats)
        "require_mention": false,             # respond to all messages (no mention needed)
        "welcome_message": "Hi! I'm your tutor."
    }
"""

import asyncio
import logging

import httpx

from app.channels.base import BaseChannelAdapter
from app.channels.base import ChannelConfig
from app.channels.base import InboundMessage

log = logging.getLogger("learnharness.channels.telegram")

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"


class TelegramAdapter(BaseChannelAdapter):
    platform_name = "telegram"

    def __init__(self, config: ChannelConfig, tg_config: dict):
        super().__init__(config, tg_config)
        self.token = tg_config["token"]
        self.api_base = TELEGRAM_API_BASE.format(token=self.token)
        self.welcome = tg_config.get("welcome_message")
        self._offset = 0
        self._polling = False
        self._seen_users: set[str] = set()

    async def connect(self) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{self.api_base}/getMe")
            resp.raise_for_status()
            bot_info = resp.json()["result"]
            self._bot_user_id = str(bot_info.get("id", ""))
            log.info(
                "Telegram connected as @%s (%s)",
                bot_info.get("username"),
                bot_info.get("id"),
            )

    async def disconnect(self) -> None:
        self._polling = False

    async def send_message(self, channel_id: str, text: str) -> None:
        chunks = []
        while text:
            chunks.append(text[:4000])
            text = text[4000:]

        async with httpx.AsyncClient(timeout=30) as client:
            for chunk in chunks:
                resp = await client.post(
                    f"{self.api_base}/sendMessage",
                    json={
                        "chat_id": channel_id,
                        "text": chunk,
                        "parse_mode": "Markdown",
                    },
                )
                if not resp.is_success:
                    resp = await client.post(
                        f"{self.api_base}/sendMessage",
                        json={"chat_id": channel_id, "text": chunk},
                    )
                await asyncio.sleep(0.05)

    async def listen(self) -> None:
        self._polling = True

        while self._polling:
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.get(
                        f"{self.api_base}/getUpdates",
                        params={"offset": self._offset, "timeout": 30},
                    )
                    resp.raise_for_status()
                    data = resp.json()

                updates = data.get("result", [])
                for update in updates:
                    self._offset = update["update_id"] + 1

                    message = update.get("message") or update.get("edited_message")
                    if not message:
                        continue

                    chat = message.get("chat", {})
                    chat_id = chat.get("id")
                    chat_type = chat.get("type", "private")
                    text = message.get("text", "")

                    if not text or chat_id is None:
                        continue

                    from_user = message.get("from", {})
                    user_id = str(from_user.get("id", ""))
                    username = from_user.get("username", "")
                    first_name = from_user.get("first_name", "")
                    sender_name = username or first_name or "user"

                    is_dm = chat_type == "private"

                    inbound = InboundMessage(
                        text=text,
                        sender_name=sender_name,
                        sender_id=user_id,
                        channel_id=str(chat_id),
                        platform="telegram",
                        is_dm=is_dm,
                        metadata={
                            "username": username,
                            "chat_type": chat_type,
                        },
                    )

                    # Access control check
                    allowed, reason = self.check_access(inbound, is_mentioned=True)
                    if not allowed:
                        log.debug("Telegram: denying %s (%s) — %s", sender_name, user_id, reason)
                        continue

                    # Welcome message for new users
                    if self.welcome and user_id not in self._seen_users:
                        self._seen_users.add(user_id)
                        await self.send_message(str(chat_id), self.welcome)

                    asyncio.create_task(self.handle_inbound(inbound))

            except httpx.ReadTimeout:
                continue
            except Exception:
                log.exception("Telegram polling error")
                await asyncio.sleep(5)
