"""Tests for channel adapters — base classes, access control, and IRC parsing."""

from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest

from app.channels.base import AccessControl
from app.channels.base import BaseChannelAdapter
from app.channels.base import ChannelConfig
from app.channels.base import InboundMessage


class TestAccessControl:
    """Test the AccessControl class — user filtering, DM permissions, channel restrictions."""

    def test_default_allows_everyone(self):
        ac = AccessControl.from_config({})
        assert ac.is_user_allowed("123", "anyone") is True
        assert ac.allow_dms is True
        assert ac.require_mention is True

    def test_user_allowlist_by_username(self):
        ac = AccessControl.from_config({"allowed_users": ["mattf", "jane"]})
        assert ac.is_user_allowed("1", "mattf") is True
        assert ac.is_user_allowed("2", "jane") is True
        assert ac.is_user_allowed("3", "unknown") is False

    def test_user_allowlist_by_id(self):
        ac = AccessControl.from_config({"allowed_users": ["12345"]})
        assert ac.is_user_allowed("12345", "someone") is True
        assert ac.is_user_allowed("99999", "someone") is False

    def test_blocklist_overrides_allowlist(self):
        ac = AccessControl.from_config({"allowed_users": ["mattf"], "blocked_users": ["mattf"]})
        assert ac.is_user_allowed("1", "mattf") is False

    def test_blocklist_alone(self):
        ac = AccessControl.from_config({"blocked_users": ["spammer"]})
        assert ac.is_user_allowed("1", "spammer") is False
        assert ac.is_user_allowed("2", "good_user") is True

    def test_case_insensitive(self):
        ac = AccessControl.from_config({"allowed_users": ["@MattF"]})
        assert ac.is_user_allowed("1", "mattf") is True
        assert ac.is_user_allowed("1", "MATTF") is True
        assert ac.is_user_allowed("1", "@mattf") is True

    def test_dm_permissions(self):
        ac = AccessControl.from_config({"allow_dms": False})
        allowed, reason = ac.should_respond("1", "user", "#chan", True, True)
        assert allowed is False
        assert "DM" in reason

        allowed, _ = ac.should_respond("1", "user", "#chan", False, True)
        assert allowed is True

    def test_require_mention_channels_only(self):
        ac = AccessControl.from_config({"require_mention": True})
        # Not mentioned in channel → blocked
        allowed, _ = ac.should_respond("1", "user", "#chan", False, False)
        assert allowed is False
        # Mentioned in channel → allowed
        allowed, _ = ac.should_respond("1", "user", "#chan", False, True)
        assert allowed is True
        # DM → always allowed (mention bypassed)
        allowed, _ = ac.should_respond("1", "user", "nick", True, False)
        assert allowed is True

    def test_channel_allowlist(self):
        ac = AccessControl.from_config({"allowed_channels": ["#learn", "123"]})
        assert ac.is_channel_allowed("#learn") is True
        assert ac.is_channel_allowed("#random") is False
        assert ac.is_channel_allowed("123") is True

    def test_channel_allowlist_empty_allows_all(self):
        ac = AccessControl.from_config({})
        assert ac.is_channel_allowed("#anything") is True

    def test_full_check_allowed(self):
        ac = AccessControl.from_config(
            {
                "allowed_users": ["mattf"],
                "allow_dms": True,
                "require_mention": True,
                "allowed_channels": ["#learn"],
            }
        )
        allowed, reason = ac.should_respond("1", "mattf", "#learn", False, True)
        assert allowed is True
        assert reason == "OK"

    def test_full_check_blocked_user(self):
        ac = AccessControl.from_config({"allowed_users": ["mattf"]})
        allowed, reason = ac.should_respond("1", "hacker", "#learn", False, True)
        assert allowed is False
        assert "not in allowed" in reason


class TestInboundMessage:
    """Test InboundMessage dataclass."""

    def test_defaults(self):
        msg = InboundMessage(
            text="hello",
            sender_name="user",
            sender_id="123",
            channel_id="#test",
            platform="irc",
        )
        assert msg.is_dm is False
        assert msg.metadata == {}

    def test_with_metadata(self):
        msg = InboundMessage(
            text="hello",
            sender_name="user",
            sender_id="123",
            channel_id="#test",
            platform="discord",
            is_dm=True,
            metadata={"guild_id": "456"},
        )
        assert msg.is_dm is True
        assert msg.metadata["guild_id"] == "456"


class TestChannelConfig:
    """Test ChannelConfig dataclass."""

    def test_defaults(self):
        cc = ChannelConfig(
            agent_id="agent-1",
            agent_name="Test Agent",
            master_prompt="You are a test agent.",
        )
        assert cc.api_base == "http://api:8000"
        assert cc.llm_model is None


class TestBaseChannelAdapter:
    """Test the base adapter lifecycle and access control integration."""

    def _make_adapter(self, platform_config=None):
        """Create a concrete adapter for testing."""
        platform_config = platform_config or {}

        class TestAdapter(BaseChannelAdapter):
            platform_name = "test"

            async def connect(self):
                pass

            async def disconnect(self):
                pass

            async def send_message(self, channel_id, text):
                pass

        cc = ChannelConfig(
            agent_id="agent-1",
            agent_name="Test",
            master_prompt="Test prompt",
            api_base="http://localhost:8000",
        )
        return TestAdapter(cc, platform_config)

    def test_check_access_allows_by_default(self):
        adapter = self._make_adapter()
        msg = InboundMessage(
            text="hello",
            sender_name="user",
            sender_id="123",
            channel_id="#test",
            platform="test",
            is_dm=False,
        )
        allowed, _ = adapter.check_access(msg, is_mentioned=True)
        assert allowed is True

    def test_check_access_blocks_non_mentioned(self):
        adapter = self._make_adapter({"require_mention": True})
        msg = InboundMessage(
            text="hello",
            sender_name="user",
            sender_id="123",
            channel_id="#test",
            platform="test",
            is_dm=False,
        )
        allowed, reason = adapter.check_access(msg, is_mentioned=False)
        assert allowed is False
        assert "mention" in reason.lower()

    def test_check_access_allows_dm_without_mention(self):
        adapter = self._make_adapter({"require_mention": True})
        msg = InboundMessage(
            text="hello",
            sender_name="user",
            sender_id="123",
            channel_id="user_nick",
            platform="test",
            is_dm=True,
        )
        allowed, _ = adapter.check_access(msg, is_mentioned=False)
        assert allowed is True

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self):
        adapter = self._make_adapter()
        await adapter.start()
        assert adapter._running is True
        assert adapter._outbound_task is not None
        await adapter.stop()
        assert adapter._running is False

    @pytest.mark.asyncio
    async def test_ensure_learner_failure(self):
        adapter = self._make_adapter()
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("connection failed")
            )
            result = await adapter._ensure_learner("test_user")
            assert result is None
