"""Test agent models and creation."""

import uuid

from app.models import Agent


def test_agent_creation():
    agent = Agent(
        id=str(uuid.uuid4()),
        name="Test Tutor",
        master_prompt="You are a tutor. Teach whatever the user asks.",
        tools=["web_search", "wikipedia"],
        channels={},
        heartbeat_interval=300,
    )
    assert agent.name == "Test Tutor"
    assert "web_search" in agent.tools
    assert agent.heartbeat_interval == 300


def test_agent_generic_prompt():
    agent = Agent(
        id=str(uuid.uuid4()),
        name="German Buddy",
        master_prompt="You are a friendly German tutor. Only respond in German.",
        tools=[],
        channels={"irc": {"host": "irc.libera.chat", "channel": "#german"}},
    )
    assert "German" in agent.master_prompt
    assert "irc" in agent.channels
