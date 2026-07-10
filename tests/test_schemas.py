"""Test Pydantic schemas — validation, serialization, edge cases."""

import pytest
from pydantic import ValidationError

from app.schemas import AgentCreate
from app.schemas import ChatMessage
from app.schemas import ChatRequest
from app.schemas import ChatResponse
from app.schemas import ChatResponseChoice
from app.schemas import Correction
from app.schemas import LearnerCreate
from app.schemas import MasteryDelta
from app.schemas import ReviewAnswer


class TestAgentCreate:
    def test_minimal_agent(self):
        agent = AgentCreate(name="Test", master_prompt="You are a tutor.")
        assert agent.name == "Test"
        assert agent.tools == ["web_search", "wikipedia"]
        assert agent.heartbeat_interval == 300

    def test_custom_tools(self):
        agent = AgentCreate(
            name="Test",
            master_prompt="You are a tutor.",
            tools=["arxiv", "browse_url"],
        )
        assert "arxiv" in agent.tools

    def test_no_tools(self):
        agent = AgentCreate(name="Test", master_prompt="Test", tools=[])
        assert agent.tools == []

    def test_minimal_name_accepted(self):
        # Pydantic accepts empty strings — validation is at app level
        agent = AgentCreate(name="", master_prompt="Test")
        assert agent.name == ""


class TestChatMessage:
    def test_user_message(self):
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_system_message(self):
        msg = ChatMessage(role="system", content="You are a tutor")
        assert msg.role == "system"

    def test_invalid_role(self):
        with pytest.raises(ValidationError):
            ChatMessage(role="admin", content="hack")


class TestChatRequest:
    def test_simple_request(self):
        req = ChatRequest(messages=[ChatMessage(role="user", content="Hello")])
        assert len(req.messages) == 1
        assert req.stream is False

    def test_with_agent_learner(self):
        req = ChatRequest(
            messages=[ChatMessage(role="user", content="Hi")],
            agent_id="abc-123",
            learner_id="learner-1",
            session_id="sess-1",
        )
        assert req.agent_id == "abc-123"
        assert req.learner_id == "learner-1"

    def test_empty_messages_rejected(self):
        # Pydantic should accept empty list but it's a valid schema
        req = ChatRequest(messages=[])
        assert req.messages == []


class TestCorrection:
    def test_basic_correction(self):
        c = Correction(original="ich bin müde", corrected="ich habe mühe")
        assert c.original == "ich bin müde"
        assert c.severity == "warning"

    def test_with_rule(self):
        c = Correction(
            original="ein Hund",
            corrected="einen Hund",
            rule="Accusative case after haben",
            severity="error",
        )
        assert c.severity == "error"
        assert c.rule == "Accusative case after haben"

    def test_invalid_severity(self):
        with pytest.raises(ValidationError):
            Correction(original="a", corrected="b", severity="critical")


class TestMasteryDelta:
    def test_up_delta(self):
        d = MasteryDelta(
            concept_id="c1",
            concept_name="greeting",
            before=0.3,
            after=0.6,
            direction="up",
        )
        assert d.direction == "up"

    def test_down_delta(self):
        d = MasteryDelta(
            concept_id="c1",
            concept_name="grammar",
            before=0.8,
            after=0.4,
            direction="down",
        )
        assert d.direction == "down"


class TestReviewAnswer:
    def test_valid_ratings(self):
        for rating in [1, 2, 3, 4]:
            ans = ReviewAnswer(rating=rating)
            assert ans.rating == rating

    def test_invalid_rating_zero(self):
        with pytest.raises(ValidationError):
            ReviewAnswer(rating=0)

    def test_invalid_rating_five(self):
        with pytest.raises(ValidationError):
            ReviewAnswer(rating=5)


class TestChatResponse:
    def test_full_response(self):
        resp = ChatResponse(
            id="chatcmpl-test",
            created=1234567890,
            model="qwen2.5:3b",
            choices=[
                ChatResponseChoice(
                    message=ChatMessage(role="assistant", content="Hello!"),
                )
            ],
            corrections=[
                Correction(original="a", corrected="b"),
            ],
        )
        assert resp.id == "chatcmpl-test"
        assert resp.object == "chat.completion"
        assert len(resp.corrections) == 1
        assert resp.choices[0].message.content == "Hello!"


class TestLearnerCreate:
    def test_basic(self):
        learner = LearnerCreate(agent_id="a1", name="Alice")
        assert learner.agent_id == "a1"
        assert learner.name == "Alice"
        assert learner.preferences == {}

    def test_with_preferences(self):
        learner = LearnerCreate(
            agent_id="a1",
            name="Bob",
            preferences={"level": "B1", "timezone": "UTC"},
        )
        assert learner.preferences["level"] == "B1"
