"""Base classes and shared utilities for channel adapters.

Access control model:
    - allowed_users: list of usernames/IDs that can talk to the bot.
      Empty/null = allow everyone.
    - blocked_users: always blocked, even if in allowed_users.
    - allow_dms: whether the bot responds in DMs (default: true).
    - allowed_channels: restrict which channels the bot is active in.
      Empty/null = respond in any channel it's in.
    - require_mention: in channels, only respond when mentioned (default: true).
      Does not affect DMs.

Example agent.channels config:
    {
        "irc": {
            "host": "irc.libera.chat",
            "nick": "LearnBot",
            "channels": ["#learn"],
            "allowed_users": ["mattf", "jane"],
            "allow_dms": true,
            "require_mention": true
        },
        "telegram": {
            "token": "...",
            "allowed_users": ["@mattf"],
            "allowed_chat_ids": [-100123],
            "allow_dms": false
        },
        "discord": {
            "token": "...",
            "allowed_channels": [123, 456],
            "allowed_users": ["1234567890"],
            "allow_dms": true,
            "require_mention": true
        }
    }
"""

import asyncio
import logging
from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from dataclasses import field

import httpx

log = logging.getLogger("learnharness.channels")


@dataclass
class ChannelConfig:
    """Configuration for a channel adapter, derived from an agent's channels dict."""

    agent_id: str
    agent_name: str
    master_prompt: str
    api_base: str = "http://api:8000"
    llm_model: str | None = None


@dataclass
class InboundMessage:
    """A message received from a channel."""

    text: str
    sender_name: str
    sender_id: str  # platform-native user ID (nick, telegram user id, discord user id)
    channel_id: str  # IRC channel, Telegram chat_id, Discord channel_id
    platform: str  # "irc", "telegram", "discord"
    is_dm: bool = False  # True if this is a direct/private message
    metadata: dict = field(default_factory=dict)


@dataclass
class AccessControl:
    """Per-channel access control rules. Parsed from the platform config dict."""

    allow_dms: bool = True
    require_mention: bool = True
    allowed_users: set[str] = field(default_factory=set)  # empty = allow all
    blocked_users: set[str] = field(default_factory=set)
    allowed_channels: set[str] = field(default_factory=set)  # empty = allow all

    @classmethod
    def from_config(cls, platform_config: dict) -> "AccessControl":
        """Build access control from a platform config dict."""
        return cls(
            allow_dms=platform_config.get("allow_dms", True),
            require_mention=platform_config.get("require_mention", True),
            allowed_users={
                str(u).lower().lstrip("@") for u in platform_config.get("allowed_users", [])
            },
            blocked_users={
                str(u).lower().lstrip("@") for u in platform_config.get("blocked_users", [])
            },
            allowed_channels={str(c).lower() for c in platform_config.get("allowed_channels", [])},
        )

    def is_user_allowed(self, user_id: str, username: str = "") -> bool:
        """Check if a user is allowed to talk to the bot."""
        uid = str(user_id).lower()
        uname = username.lower().lstrip("@")

        # Blocked users are always blocked
        if uid in self.blocked_users or uname in self.blocked_users:
            return False

        # If no allowlist, everyone is allowed
        if not self.allowed_users:
            return True

        # Check allowlist — match on either user ID or username
        return uid in self.allowed_users or uname in self.allowed_users

    def is_channel_allowed(self, channel_id: str) -> bool:
        """Check if the bot should be active in this channel."""
        if not self.allowed_channels:
            return True
        return str(channel_id).lower() in self.allowed_channels

    def should_respond(
        self,
        user_id: str,
        username: str,
        channel_id: str,
        is_dm: bool,
        is_mentioned: bool,
    ) -> tuple[bool, str]:
        """Full access check. Returns (allowed, reason)."""
        # Check user allowlist/blocklist
        if not self.is_user_allowed(user_id, username):
            return False, f"User '{username}' not in allowed list or is blocked"

        # Check DM permissions
        if is_dm and not self.allow_dms:
            return False, "DMs not allowed for this channel"

        # Check channel allowlist (for non-DMs)
        if not is_dm and not self.is_channel_allowed(channel_id):
            return False, f"Channel '{channel_id}' not in allowed list"

        # Check mention requirement (channels only, not DMs)
        if not is_dm and self.require_mention and not is_mentioned:
            return False, "Bot not mentioned and require_mention is true"

        return True, "OK"


class BaseChannelAdapter(ABC):
    """Base class for all channel adapters.

    Each adapter:
    - Connects to its platform (IRC server, Telegram, Discord)
    - Listens for incoming messages
    - Checks access control (user allowlist, DM permissions, channel restrictions)
    - Forwards allowed messages to the LearnHarness API
    - Sends the agent's response back
    - Polls for outbound (proactive) messages
    """

    platform_name: str = "base"

    def __init__(self, config: ChannelConfig, platform_config: dict):
        self.config = config
        self.platform_config = platform_config
        self.access = AccessControl.from_config(platform_config)
        self.learner_map: dict[str, str] = {}  # platform_user_key → learner_id
        self.session_map: dict[str, str] = {}  # channel_id → session_id
        self._outbound_task: asyncio.Task | None = None
        self._running = False
        self._bot_user_id: str = ""  # set by subclass for mention detection

    @abstractmethod
    async def connect(self) -> None:
        """Connect to the platform."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the platform."""
        ...

    @abstractmethod
    async def send_message(self, channel_id: str, text: str) -> None:
        """Send a message to a specific channel/chat on this platform."""
        ...

    async def start(self) -> None:
        """Start the adapter — connect and begin polling."""
        self._running = True
        await self.connect()
        log.info(
            "%s adapter connected for agent '%s' (allow_dms=%s, allowed_users=%d, "
            "allowed_channels=%d, require_mention=%s)",
            self.platform_name,
            self.config.agent_name,
            self.access.allow_dms,
            len(self.access.allowed_users),
            len(self.access.allowed_channels),
            self.access.require_mention,
        )
        self._outbound_task = asyncio.create_task(self._poll_outbound())

    async def stop(self) -> None:
        """Stop the adapter."""
        self._running = False
        if self._outbound_task:
            self._outbound_task.cancel()
        await self.disconnect()
        log.info("%s adapter stopped", self.platform_name)

    def check_access(
        self,
        msg: InboundMessage,
        is_mentioned: bool = True,
    ) -> tuple[bool, str]:
        """Check if this message should be processed.

        Returns (allowed, reason_if_denied).
        """
        return self.access.should_respond(
            user_id=msg.sender_id,
            username=msg.sender_name,
            channel_id=msg.channel_id,
            is_dm=msg.is_dm,
            is_mentioned=is_mentioned,
        )

    async def handle_inbound(self, msg: InboundMessage) -> None:
        """Forward an inbound message to the API and send the response back.

        This is the core integration point — calls the LearnHarness chat endpoint.
        Access control should be checked by the subclass BEFORE calling this.
        """
        user_key = f"{self.platform_name}:{msg.sender_id or msg.sender_name}"

        learner_id = self.learner_map.get(user_key)
        session_key = f"{self.platform_name}:{msg.channel_id}"
        session_id = self.session_map.get(session_key, f"sess_{session_key}")

        payload = {
            "agent_id": self.config.agent_id,
            "session_id": session_id,
            "messages": [{"role": "user", "content": msg.text}],
        }

        try:
            # Create learner on first message
            if not learner_id:
                learner_id = await self._ensure_learner(msg.sender_name)
                if learner_id:
                    self.learner_map[user_key] = learner_id

            # Include learner_id if we have one (avoids dict key overwrite smell)
            if learner_id:
                payload["learner_id"] = learner_id

            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{self.config.api_base}/v1/chat/completions",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

            self.session_map[session_key] = session_id

            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content:
                await self.send_message(msg.channel_id, content)

        except Exception:
            log.exception("Error processing inbound %s message", self.platform_name)
            await self.send_message(msg.channel_id, "Sorry, I encountered an error.")

    async def _ensure_learner(self, name: str) -> str | None:
        """Create a learner via the API."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.config.api_base}/v1/learners",
                    json={"agent_id": self.config.agent_id, "name": name},
                )
                resp.raise_for_status()
                return resp.json().get("id")
        except Exception:
            log.exception("Failed to create learner")
            return None

    async def _poll_outbound(self) -> None:
        """Poll the API for outbound messages and deliver them."""
        while self._running:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(
                        f"{self.config.api_base}/v1/outbound",
                        params={
                            "channel": self.platform_name,
                            "agent_id": self.config.agent_id,
                        },
                    )
                    resp.raise_for_status()
                    messages = resp.json()

                for msg in messages:
                    target = msg.get("extra", {}).get("target_channel")
                    if not target:
                        for ch_id in set(self.session_map.values()):
                            await self.send_message(ch_id, msg["message"])
                    else:
                        await self.send_message(target, msg["message"])

                    async with httpx.AsyncClient(timeout=10) as client:
                        await client.post(f"{self.config.api_base}/v1/outbound/{msg['id']}/sent")

            except Exception:
                log.warning("Outbound poll failed for %s", self.platform_name, exc_info=True)

            await asyncio.sleep(30)
