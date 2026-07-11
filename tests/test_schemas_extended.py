"""Tests for the schemas (Pydantic models) — request/response validation."""

import pytest
from pydantic import ValidationError

from app.schemas import AgentOut
from app.schemas import ConceptCreate
from app.schemas import OutboundMessageOut


class TestConceptCreate:
    """Test the ConceptCreate request body model."""

    def test_valid(self):
        cc = ConceptCreate(
            agent_id="agent-1",
            name="Present Tense",
            category="grammar",
            difficulty=3,
        )
        assert cc.agent_id == "agent-1"
        assert cc.name == "Present Tense"

    def test_with_description(self):
        cc = ConceptCreate(
            agent_id="agent-1",
            name="Ser vs Estar",
            category="grammar",
            difficulty=4,
            description="Distinguishing between ser and estar",
        )
        assert cc.description is not None

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            ConceptCreate(name="Test", category="grammar")


class TestOutboundMessageOut:
    """Test OutboundMessageOut includes the extra field."""

    def test_has_extra_field(self):
        msg = OutboundMessageOut(
            id=1,
            agent_id="agent-1",
            learner_id=None,
            channel="irc",
            message="hello",
            extra={"type": "review_reminder"},
            sent=False,
            created_at="2024-01-01T00:00:00Z",
        )
        assert msg.extra["type"] == "review_reminder"

    def test_extra_defaults_to_empty(self):
        msg = OutboundMessageOut(
            id=1,
            agent_id="agent-1",
            learner_id=None,
            channel="irc",
            message="hello",
            sent=False,
            created_at="2024-01-01T00:00:00Z",
        )
        assert msg.extra == {}


class TestAgentOutMasking:
    """Test AgentOut.from_agent() masks sensitive fields."""

    def test_from_agent_masks_tokens(self):
        from datetime import datetime, timezone

        from app.models import Agent

        agent = Agent(
            id="agent-1",
            name="Test Agent",
            master_prompt="You are a test agent.",
            tools=[],
            channels={
                "telegram": {"token": "123456:ABC-DEF"},
                "discord": {"token": "MTIzNDU2"},
            },
            heartbeat_interval=3600,
            active=True,
            created_at=datetime.now(timezone.utc),
        )
        out = AgentOut.from_agent(agent)
        channels = out.channels
        if "telegram" in channels:
            assert channels["telegram"].get("token") != "123456:ABC-DEF"
        if "discord" in channels:
            assert channels["discord"].get("token") != "MTIzNDU2"

    def test_from_agent_preserves_non_sensitive(self):
        from datetime import datetime, timezone

        from app.models import Agent

        agent = Agent(
            id="agent-1",
            name="Test Agent",
            master_prompt="You are a test agent.",
            tools=[],
            channels={
                "irc": {"host": "localhost", "port": 6667, "channels": ["#learn"]},
            },
            heartbeat_interval=3600,
            active=True,
            created_at=datetime.now(timezone.utc),
        )
        out = AgentOut.from_agent(agent)
        assert out.channels["irc"]["host"] == "localhost"
        assert out.channels["irc"]["port"] == 6667
