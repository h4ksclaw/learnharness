"""Discord channel adapter.

Uses the Discord Gateway WebSocket + REST API. Minimal deps — uses httpx
for REST and raw asyncio websocket for Gateway.

Config (from agent.channels["discord"]):
    {
        "token": "MTIzNDU2...",           # bot token
        "allowed_channels": [123456789],  # optional whitelist of channel IDs
        "prefix": "!"                     # optional command prefix
    }

Note: For production, prefer discord.py. This is a lightweight implementation
that avoids the dependency but handles the core flow.
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
        super().__init__(config)
        self.dc_config = dc_config
        self.token = dc_config["token"]
        self.allowed_channels = set(dc_config.get("allowed_channels", []))
        self.headers = {"Authorization": f"Bot {self.token}"}
        self._bot_user_id: str | None = None
        self._session_id: str | None = None
        self._seq: int | None = None
        self._ws = None  # websockets.WebSocketClientProtocol

    async def connect(self) -> None:
        # Get bot info
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{DISCORD_API}/users/@me", headers=self.headers)
            resp.raise_for_status()
            bot = resp.json()
            self._bot_user_id = bot["id"]
            log.info("Discord connected as %s (%s)", bot.get("username"), bot["id"])

        # Connect to gateway
        await self._gateway_connect()

    async def _gateway_connect(self) -> None:
        """Connect to Discord Gateway via WebSocket."""
        import websockets

        gateway_url = "wss://gateway.discord.gg/?v=10&encoding=json"

        self._ws = await websockets.connect(gateway_url)

        # Receive Hello
        hello = json.loads(await self._ws.recv())
        heartbeat_interval = hello["d"]["heartbeat_interval"] / 1000
        log.debug("Discord heartbeat interval: %sms", heartbeat_interval)

        # Start heartbeat
        asyncio.create_task(self._heartbeat(heartbeat_interval))

        # We'll identify in the listen loop

    async def _heartbeat(self, interval_ms: float) -> None:
        """Send heartbeats to keep the gateway connection alive."""
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
        """Send a message to a Discord channel."""
        # Discord limit: 2000 chars per message
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
                await asyncio.sleep(0.3)  # Rate limit: 5 msg/sec per channel

    async def listen(self) -> None:
        """Main Discord Gateway listen loop."""
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

                if op == 10:  # Hello — already handled, send Identify
                    pass
                elif op == 0:  # Dispatch
                    event_name = payload.get("t")

                    if event_name == "READY":
                        self._session_id = data.get("session_id")
                        log.info("Discord READY — %s", data.get("user", {}).get("username"))
                        continue

                    if event_name == "MESSAGE_CREATE":
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
        """Handle an incoming Discord message."""
        # Ignore bot messages
        author = data.get("author", {})
        if author.get("bot"):
            return

        channel_id = data["channel_id"]
        text = data.get("content", "").strip()
        if not text:
            return

        # Check whitelist
        if self.allowed_channels and int(channel_id) not in self.allowed_channels:
            return

        # Check if mentioned or DM
        is_dm = "@" not in data.get("channel_id", "")
        mentioned = self._bot_user_id in text if self._bot_user_id else False

        # Check for mentions in the mentions array
        for mention in data.get("mentions", []):
            if mention.get("id") == self._bot_user_id:
                mentioned = True
                break

        if not is_dm and not mentioned:
            return

        # Clean the text — remove mention
        clean_text = text.replace(f"<@{self._bot_user_id}>", "").strip()
        clean_text = clean_text.replace(f"<@!{self._bot_user_id}>", "").strip()
        if not clean_text:
            clean_text = "hello"

        sender_name = author.get("global_name") or author.get("username", "user")

        inbound = InboundMessage(
            text=clean_text,
            sender_name=sender_name,
            channel_id=channel_id,
            platform="discord",
            metadata={
                "user_id": author.get("id"),
                "channel_id": channel_id,
                "message_id": data.get("id"),
            },
        )
        asyncio.create_task(self.handle_inbound(inbound))
