"""IRC channel adapter.

Connects to an IRC server, listens in configured channels, and forwards
messages to the LearnHarness API. Uses raw socket protocol — no deps.

Config (from agent.channels["irc"]):
    {
        "host": "irc.libera.chat",
        "port": 6667,
        "nick": "LearnBot",
        "channels": ["#learnharness"],
        "password": null,         # NickServ password (optional)
        "prefix": "!",            # command prefix (optional, default: direct mention)
        "ssl": false              # use SSL (optional)
    }
"""

import asyncio
import contextlib
import logging
import ssl

from app.channels.base import BaseChannelAdapter
from app.channels.base import ChannelConfig
from app.channels.base import InboundMessage

log = logging.getLogger("learnharness.channels.irc")


class IRCAdapter(BaseChannelAdapter):
    platform_name = "irc"

    def __init__(self, config: ChannelConfig, irc_config: dict):
        super().__init__(config)
        self.irc_config = irc_config
        self.host = irc_config.get("host", "irc.libera.chat")
        self.port = irc_config.get("port", 6667)
        self.nick = irc_config.get("nick", "LearnHarnessBot")
        self.channels = irc_config.get("channels", [])
        self.password = irc_config.get("password")
        self.use_ssl = irc_config.get("ssl", False)
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None

    async def connect(self) -> None:
        ssl_ctx = ssl.create_default_context() if self.use_ssl else None

        self.reader, self.writer = await asyncio.open_connection(self.host, self.port, ssl=ssl_ctx)

        # Register
        self._send_raw(f"NICK {self.nick}")
        self._send_raw(f"USER {self.nick} 0 * :{self.config.agent_name}")

        # NickServ auth
        if self.password:
            await asyncio.sleep(1)
            self._send_raw(f"PRIVMSG NickServ :IDENTIFY {self.nick} {self.password}")

        log.info("IRC connected to %s as %s", self.host, self.nick)

    async def disconnect(self) -> None:
        if self.writer:
            self._send_raw("QUIT :LearnHarness signing off")
            self.writer.close()
            with contextlib.suppress(Exception):
                await self.writer.wait_closed()
        self.writer = None
        self.reader = None

    def _send_raw(self, line: str) -> None:
        if self.writer:
            self.writer.write(f"{line}\r\n".encode())
            log.debug("IRC → %s", line)

    async def send_message(self, channel_id: str, text: str) -> None:
        """Send a message to an IRC channel or user."""
        # IRC limit: 512 bytes per message including headers
        # Split long messages
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Truncate to ~400 chars per message
            while line:
                chunk = line[:400]
                line = line[400:]
                self._send_raw(f"PRIVMSG {channel_id} :{chunk}")
                if self.writer:
                    await self.writer.drain()
                await asyncio.sleep(0.3)  # Rate limit

    async def listen(self) -> None:
        """Main IRC listen loop — called by the channel manager."""
        while self._running and self.reader:
            try:
                raw = await self.reader.readline()
                if not raw:
                    log.warning("IRC connection closed")
                    break

                line = raw.decode(errors="replace").strip()
                log.debug("IRC ← %s", line)

                # Handle PING/PONG
                if line.startswith("PING"):
                    self._send_raw(line.replace("PING", "PONG", 1))
                    continue

                # Parse PRIVMSG
                if " PRIVMSG " not in line:
                    continue

                # Parse: :nick!user@host PRIVMSG #channel :message
                try:
                    prefix, rest = line[1:].split(" ", 1)
                    nick = prefix.split("!")[0]
                    parts = rest.split(" ", 2)
                    cmd = parts[0]
                    target = parts[1]
                    msg_text = parts[2][1:] if len(parts) > 2 else ""

                    # Only handle channel messages or direct messages
                    if cmd != "PRIVMSG":
                        continue

                    # Respond in channel if mentioned, or to bot directly
                    is_dm = target == self.nick
                    is_mentioned = self.nick.lower() in msg_text.lower()

                    if not is_dm and not is_mentioned:
                        # Still join configured channels
                        continue

                    # Remove the bot nick from the message
                    clean_text = msg_text.replace(self.nick, "").strip()
                    if clean_text.startswith(":"):
                        clean_text = clean_text[1:].strip()
                    if not clean_text:
                        continue

                    # Use the channel where the message came from
                    reply_target = nick if is_dm else target

                    inbound = InboundMessage(
                        text=clean_text,
                        sender_name=nick,
                        channel_id=reply_target,
                        platform="irc",
                        metadata={"user_id": nick},
                    )
                    asyncio.create_task(self.handle_inbound(inbound))

                except (ValueError, IndexError):
                    continue

            except Exception:
                log.exception("IRC listen error")
                break

        # Auto-reconnect
        if self._running:
            log.info("IRC reconnecting in 5s...")
            await asyncio.sleep(5)
            try:
                await self.connect()
                # Rejoin channels
                for ch in self.channels:
                    self._send_raw(f"JOIN {ch}")
                await self.listen()
            except Exception:
                log.exception("IRC reconnect failed")

    async def join_channels(self) -> None:
        """Join all configured channels after registration."""
        await asyncio.sleep(2)
        for ch in self.channels:
            self._send_raw(f"JOIN {ch}")
            log.info("IRC joined %s", ch)
