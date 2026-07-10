"""Telegram channel adapter.

Uses the Telegram Bot API (long polling). No external deps — pure httpx.

Config (from agent.channels["telegram"]):
    {
        "token": "123456:ABC-DEF...",
        "allowed_chat_ids": [-1001234567890],   # optional whitelist
        "welcome_message": "Hi! I'm your tutor."  # optional
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
        super().__init__(config)
        self.tg_config = tg_config
        self.token = tg_config["token"]
        self.api_base = TELEGRAM_API_BASE.format(token=self.token)
        self.allowed_chats = set(tg_config.get("allowed_chat_ids", []))
        self.welcome = tg_config.get("welcome_message")
        self._offset = 0
        self._polling = False

    async def connect(self) -> None:
        # Verify token
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{self.api_base}/getMe")
            resp.raise_for_status()
            bot_info = resp.json()["result"]
            log.info(
                "Telegram connected as @%s (%s)",
                bot_info.get("username"),
                bot_info.get("id"),
            )

    async def disconnect(self) -> None:
        self._polling = False

    async def send_message(self, channel_id: str, text: str) -> None:
        """Send a message to a Telegram chat."""
        # Telegram message limit: 4096 chars
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
                    # Retry without Markdown if parsing failed
                    resp = await client.post(
                        f"{self.api_base}/sendMessage",
                        json={"chat_id": channel_id, "text": chunk},
                    )
                await asyncio.sleep(0.05)  # Rate limit: ~30 msg/sec

    async def listen(self) -> None:
        """Long-polling loop for Telegram updates."""
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

                    chat_id = message["chat"]["id"]
                    text = message.get("text", "")

                    if not text:
                        continue

                    # Check whitelist
                    if self.allowed_chats and chat_id not in self.allowed_chats:
                        log.debug("Telegram: skipping unlisted chat %s", chat_id)
                        continue

                    sender_name = message["from"].get("first_name", "") or message["from"].get(
                        "username", "user"
                    )

                    inbound = InboundMessage(
                        text=text,
                        sender_name=sender_name,
                        channel_id=str(chat_id),
                        platform="telegram",
                        metadata={
                            "user_id": str(message["from"]["id"]),
                            "chat_id": chat_id,
                        },
                    )
                    asyncio.create_task(self.handle_inbound(inbound))

            except httpx.ReadTimeout:
                # Normal for long polling
                continue
            except Exception:
                log.exception("Telegram polling error")
                await asyncio.sleep(5)
