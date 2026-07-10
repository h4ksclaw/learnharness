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
        "ssl": false,             # use SSL (optional)
        "allowed_users": ["mattf"],    # restrict who can talk (empty = all)
        "blocked_users": ["spammer"], # always blocked
        "allow_dms": true,        # respond to DMs
        "require_mention": true   # only respond to mentions in channels
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
        super().__init__(config, irc_config)
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

        self._bot_user_id = self.nick

        self._send_raw(f"NICK {self.nick}")
        self._send_raw(f"USER {self.nick} 0 * :{self.config.agent_name}")

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
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            while line:
                chunk = line[:400]
                line = line[400:]
                self._send_raw(f"PRIVMSG {channel_id} :{chunk}")
                if self.writer:
                    await self.writer.drain()
                await asyncio.sleep(0.3)

    async def listen(self) -> None:
        while self._running and self.reader:
            try:
                raw = await self.reader.readline()
                if not raw:
                    log.warning("IRC connection closed")
                    break

                line = raw.decode(errors="replace").strip()
                log.debug("IRC ← %s", line)

                if line.startswith("PING"):
                    self._send_raw(line.replace("PING", "PONG", 1))
                    continue

                if " PRIVMSG " not in line:
                    continue

                try:
                    prefix, rest = line[1:].split(" ", 1)
                    nick = prefix.split("!")[0]
                    user_host = prefix.split("!")[1] if "!" in prefix else ""
                    parts = rest.split(" ", 2)
                    cmd = parts[0]
                    target = parts[1]
                    msg_text = parts[2][1:] if len(parts) > 2 else ""

                    if cmd != "PRIVMSG":
                        continue

                    is_dm = target.lower() == self.nick.lower()
                    is_mentioned = self.nick.lower() in msg_text.lower()

                    # Only respond in configured channels (not DMs)
                    if not is_dm:
                        configured = {c.lower() for c in self.channels}
                        if target.lower() not in configured:
                            continue

                    # Clean the message text
                    clean_text = msg_text.replace(self.nick, "").strip()
                    if clean_text.startswith(":"):
                        clean_text = clean_text[1:].strip()
                    if not clean_text:
                        continue

                    reply_target = nick if is_dm else target

                    inbound = InboundMessage(
                        text=clean_text,
                        sender_name=nick,
                        sender_id=nick,
                        channel_id=reply_target,
                        platform="irc",
                        is_dm=is_dm,
                        metadata={"user_host": user_host},
                    )

                    # Access control check
                    allowed, reason = self.check_access(inbound, is_mentioned=is_mentioned)
                    if not allowed:
                        log.debug("IRC: denying %s — %s", nick, reason)
                        continue

                    asyncio.create_task(self.handle_inbound(inbound))

                except (ValueError, IndexError):
                    continue

            except Exception:
                log.exception("IRC listen error")
                break

        if self._running:
            log.info("IRC reconnecting in 5s...")
            await asyncio.sleep(5)
            try:
                await self.connect()
                for ch in self.channels:
                    self._send_raw(f"JOIN {ch}")
                await self.listen()
            except Exception:
                log.exception("IRC reconnect failed")

    async def join_channels(self) -> None:
        await asyncio.sleep(2)
        for ch in self.channels:
            self._send_raw(f"JOIN {ch}")
            log.info("IRC joined %s", ch)
