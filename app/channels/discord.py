"""Discord channel adapter.

Uses the Discord Gateway WebSocket + REST API. Minimal deps — uses httpx
for REST and websockets for Gateway.

Config (from agent.channels["discord"]):
    {
        "token": "MTIzNDU2...",
        "allowed_users": ["1234567890"],     # Discord user IDs (empty = all)
        "blocked_users": ["9876543210"],
        "allowed_channels": [123456789],     # channel IDs (empty = all)
        "allow_dms": true,                   # respond to DMs
        "require_mention": true              # only respond to mentions in channels
    }
"""

import asyncio
import json
import logging

import httpx

from app.channels.base import BaseChannelAdapter
from app.channels.base import ChannelConfig
from app.channels.base import InboundMessage

log = logging.getLogger("learnharness.channels.discord")

DISCORD_API = "https://discord.com/api/v10"


class DiscordAdapter(BaseChannelAdapter):
    platform_name = "discord"

    def __init__(self, config: ChannelConfig, dc_config: dict):
        super().__init__(config, dc_config)
        self.token = dc_config["token"]
        self.headers = {"Authorization": f"Bot {self.token}"}
        self._session_id: str | None = None
        self._seq: int | None = None
        self._ws = None  # websockets.WebSocketClientProtocol

    async def connect(self) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{DISCORD_API}/users/@me", headers=self.headers)
            resp.raise_for_status()
            bot = resp.json()
            self._bot_user_id = bot["id"]
            log.info("Discord connected as %s (%s)", bot.get("username"), bot["id"])

        await self._gateway_connect()

    async def _gateway_connect(self) -> None:
        import websockets

        gateway_url = "wss://gateway.discord.gg/?v=10&encoding=json"
        self._ws = await websockets.connect(gateway_url)

        hello = json.loads(await self._ws.recv())
        heartbeat_interval = hello["d"]["heartbeat_interval"]
        log.debug("Discord heartbeat interval: %sms", heartbeat_interval)

        asyncio.create_task(self._heartbeat(heartbeat_interval))

    async def _heartbeat(self, interval_ms: float) -> None:
        interval = interval_ms / 1000
        while self._running and self._ws:
            try:
                payload = {"op": 1, "d": self._seq}
                await self._ws.send(json.dumps(payload))
                await asyncio.sleep(interval)
            except Exception:
                break

    async def disconnect(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def send_message(self, channel_id: str, text: str) -> None:
        chunks = []
        while text:
            chunks.append(text[:1900])
            text = text[1900:]

        async with httpx.AsyncClient(timeout=30) as client:
            for chunk in chunks:
                await client.post(
                    f"{DISCORD_API}/channels/{channel_id}/messages",
                    headers=self.headers,
                    json={"content": chunk},
                )
                await asyncio.sleep(0.3)

    async def listen(self) -> None:
        import websockets

        while self._running:
            try:
                if not self._ws:
                    await self._gateway_connect()

                raw = await self._ws.recv()
                payload = json.loads(raw)

                if payload.get("s"):
                    self._seq = payload["s"]

                op = payload.get("op")
                data = payload.get("d", {})

                if op == 10:  # Hello
                    pass
                elif op == 0:  # Dispatch
                    event_name = payload.get("t")

                    if event_name == "READY":
                        self._session_id = data.get("session_id")
                        log.info("Discord READY — %s", data.get("user", {}).get("username"))
                    elif event_name == "MESSAGE_CREATE":
                        await self._handle_message(data)

            except websockets.ConnectionClosed:
                log.warning("Discord WebSocket closed, reconnecting...")
                self._ws = None
                await asyncio.sleep(3)
            except Exception:
                log.exception("Discord listen error")
                self._ws = None
                await asyncio.sleep(5)

    async def _handle_message(self, data: dict) -> None:
        author = data.get("author", {})
        if author.get("bot"):
            return

        channel_id = data["channel_id"]
        text = data.get("content", "").strip()
        if not text:
            return

        user_id = author.get("id", "")
        username = author.get("global_name") or author.get("username", "user")

        # DM detection: check if this is a DM channel
        is_dm = data.get("channel_id", "") and not data.get("guild_id")

        # Mention detection
        is_mentioned = False
        for mention in data.get("mentions", []):
            if mention.get("id") == self._bot_user_id:
                is_mentioned = True
                break

        # Clean mention from text
        clean_text = text.replace(f"<@{self._bot_user_id}>", "").strip()
        clean_text = clean_text.replace(f"<@!{self._bot_user_id}>", "").strip()
        if not clean_text:
            clean_text = "hello"

        inbound = InboundMessage(
            text=clean_text,
            sender_name=username,
            sender_id=user_id,
            channel_id=channel_id,
            platform="discord",
            is_dm=is_dm,
            metadata={
                "channel_id": channel_id,
                "guild_id": data.get("guild_id"),
                "message_id": data.get("id"),
            },
        )

        # Access control check
        allowed, reason = self.check_access(inbound, is_mentioned=is_mentioned)
        if not allowed:
            log.debug("Discord: denying %s (%s) — %s", username, user_id, reason)
            return

        asyncio.create_task(self.handle_inbound(inbound))
