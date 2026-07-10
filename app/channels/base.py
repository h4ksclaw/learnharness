"""Base classes and shared utilities for channel adapters."""

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
    channel_id: str  # IRC channel, Telegram chat_id, Discord channel_id
    platform: str  # "irc", "telegram", "discord"
    metadata: dict = field(default_factory=dict)


class BaseChannelAdapter(ABC):
    """Base class for all channel adapters.

    Each adapter:
    - Connects to its platform (IRC server, Telegram, Discord)
    - Listens for incoming messages
    - Forwards them to the LearnHarness API
    - Sends the agent's response back
    - Polls for outbound (proactive) messages
    """

    platform_name: str = "base"

    def __init__(self, config: ChannelConfig):
        self.config = config
        self.learner_map: dict[str, str] = {}  # platform_user_id → learner_id
        self.session_map: dict[str, str] = {}  # channel_id → session_id
        self._outbound_task: asyncio.Task | None = None
        self._running = False

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
        log.info("%s adapter connected for agent '%s'", self.platform_name, self.config.agent_name)
        self._outbound_task = asyncio.create_task(self._poll_outbound())

    async def stop(self) -> None:
        """Stop the adapter."""
        self._running = False
        if self._outbound_task:
            self._outbound_task.cancel()
        await self.disconnect()
        log.info("%s adapter stopped", self.platform_name)

    async def handle_inbound(self, msg: InboundMessage) -> None:
        """Forward an inbound message to the API and send the response back.

        This is the core integration point — calls the LearnHarness chat endpoint.
        """
        # Build a unique key for this user on this platform
        user_key = f"{self.platform_name}:{msg.metadata.get('user_id', msg.sender_name)}"

        # Get or create learner ID
        learner_id = self.learner_map.get(user_key)
        session_key = f"{self.platform_name}:{msg.channel_id}"
        session_id = self.session_map.get(session_key, f"sess_{session_key}")

        payload = {
            "agent_id": self.config.agent_id,
            "learner_id": learner_id,
            "session_id": session_id,
            "messages": [{"role": "user", "content": msg.text}],
        }

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{self.config.api_base}/v1/chat/completions",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

            # Save learner ID for future messages
            if not learner_id:
                # Create a learner if we don't have one
                create_resp = await self._ensure_learner(msg.sender_name)
                if create_resp:
                    self.learner_map[user_key] = create_resp
                    # Resend with the new learner
                    payload["learner_id"] = create_resp
                    async with httpx.AsyncClient(timeout=120) as client:
                        resp = await client.post(
                            f"{self.config.api_base}/v1/chat/completions",
                            json=payload,
                        )
                        resp.raise_for_status()
                        data = resp.json()
                    self.learner_map[user_key] = create_resp

            self.session_map[session_key] = session_id

            # Extract response text
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
                    # Find the channel to send to
                    target = msg.get("extra", {}).get("target_channel")
                    if not target:
                        # Broadcast to all known channels
                        for ch_id in set(self.session_map.values()):
                            await self.send_message(ch_id, msg["message"])
                    else:
                        await self.send_message(target, msg["message"])

                    # Mark as sent
                    async with httpx.AsyncClient(timeout=10) as client:
                        await client.post(f"{self.config.api_base}/v1/outbound/{msg['id']}/sent")

            except Exception:
                log.debug("Outbound poll error", exc_info=True)

            await asyncio.sleep(30)
