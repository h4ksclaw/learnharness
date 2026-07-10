"""Test ORM models — creation, relationships, defaults, constraints.

Note: SQLAlchemy column defaults via mapped_column(default=X) are applied
at flush/commit time, not at construction time. Tests that check defaults
explicitly pass them, or test via the DB integration tests.
"""

import uuid

from app.models import Agent
from app.models import Concept
from app.models import ConceptEdge
from app.models import ErrorPattern
from app.models import Interaction
from app.models import Learner
from app.models import Mastery
from app.models import OutboundMessage
from app.models import ReviewItem


class TestAgent:
    def test_creation_minimal(self):
        agent = Agent(
            id=str(uuid.uuid4()),
            name="Tutor",
            master_prompt="You are a tutor.",
        )
        assert agent.name == "Tutor"
        assert agent.master_prompt == "You are a tutor."

    def test_with_all_fields(self):
        agent = Agent(
            id="test-id",
            name="Full Agent",
            master_prompt="You teach Python.",
            tools=["web_search", "arxiv", "browse_url"],
            channels={"irc": {"host": "irc.libera.chat", "channel": "#python"}},
            heartbeat_interval=600,
            llm_model="qwen2.5:7b",
            active=True,
        )
        assert len(agent.tools) == 3
        assert "irc" in agent.channels
        assert agent.llm_model == "qwen2.5:7b"
        assert agent.active is True

    def test_id_is_string(self):
        agent = Agent(id="my-custom-id", name="A", master_prompt="P")
        assert agent.id == "my-custom-id"

    def test_generic_prompt(self):
        prompt = "You are a friendly German tutor. Only respond in German."
        agent = Agent(id="a1", name="German Buddy", master_prompt=prompt)
        assert "German" in agent.master_prompt


class TestLearner:
    def test_creation_with_name(self):
        learner = Learner(id="l1", agent_id="a1", name="Alice")
        assert learner.name == "Alice"
        assert learner.agent_id == "a1"

    def test_creation_with_overall_mastery(self):
        learner = Learner(id="l1", agent_id="a1", name="Bob", overall_mastery=0.45)
        assert learner.overall_mastery == 0.45

    def test_preferences(self):
        learner = Learner(
            id="l1",
            agent_id="a1",
            name="Carol",
            preferences={"level": "B1", "timezone": "UTC"},
        )
        assert learner.preferences["level"] == "B1"


class TestConcept:
    def test_with_category(self):
        concept = Concept(
            id="c1",
            agent_id="a1",
            name="ser vs estar",
            category="grammar",
            difficulty=0.8,
        )
        assert concept.category == "grammar"
        assert concept.difficulty == 0.8

    def test_description(self):
        concept = Concept(
            id="c1",
            agent_id="a1",
            name="Present Tense",
            description="The present tense conjugation of regular verbs",
        )
        assert "conjugation" in concept.description


class TestMastery:
    def test_with_defaults(self):
        mastery = Mastery(
            learner_id="l1",
            concept_id="c1",
            p_mastery=0.5,
            p_transit=0.1,
            p_slip=0.1,
            p_guess=0.25,
        )
        assert mastery.p_mastery == 0.5
        assert mastery.p_guess == 0.25

    def test_update_values(self):
        mastery = Mastery(learner_id="l1", concept_id="c1", p_mastery=0.3)
        mastery.p_mastery = 0.8
        mastery.interactions_count = 5
        mastery.correct_count = 4
        assert mastery.p_mastery == 0.8
        assert mastery.interactions_count == 5


class TestReviewItem:
    def test_content_is_jsonb(self):
        content = {"front": "question", "back": "answer", "hint": "think!"}
        item = ReviewItem(learner_id="l1", concept_id="c1", content=content)
        assert item.content["hint"] == "think!"

    def test_fsrs_state_fields(self):
        item = ReviewItem(
            learner_id="l1",
            concept_id="c1",
            content={},
            stability=2.5,
            difficulty=0.3,
            reps=3,
            lapses=1,
            state=2,  # review state
        )
        assert item.stability == 2.5
        assert item.state == 2


class TestInteraction:
    def test_heartbeat_type(self):
        interaction = Interaction(
            learner_id=None,
            agent_id="a1",
            session_id="heartbeat",
            type="heartbeat",
        )
        assert interaction.type == "heartbeat"

    def test_chat_with_concepts(self):
        interaction = Interaction(
            learner_id="l1",
            agent_id="a1",
            session_id="s1",
            type="chat",
            user_input="Hallo",
            agent_response="Guten Tag!",
            concept_ids=["c1", "c2"],
            corrections=[{"original": "hallo", "corrected": "Hallo"}],
            tool_calls=[{"tool": "wikipedia", "args": {"query": "greetings"}}],
        )
        assert interaction.concept_ids == ["c1", "c2"]
        assert len(interaction.corrections) == 1


class TestOutboundMessage:
    def test_with_metadata(self):
        msg = OutboundMessage(
            agent_id="a1",
            learner_id="l1",
            channel="all",
            message="You have reviews due",
            extra={"type": "review_reminder", "count": 3},
        )
        assert msg.extra["type"] == "review_reminder"
        assert msg.extra["count"] == 3

    def test_learner_optional(self):
        msg = OutboundMessage(
            agent_id="a1",
            channel="irc",
            message="Broadcast!",
        )
        assert msg.learner_id is None


class TestConceptEdge:
    def test_prerequisite(self):
        edge = ConceptEdge(
            source_id="c1",
            target_id="c2",
            edge_type="prerequisite",
            weight=0.9,
        )
        assert edge.edge_type == "prerequisite"
        assert edge.weight == 0.9


class TestErrorPattern:
    def test_with_examples(self):
        pattern = ErrorPattern(
            learner_id="l1",
            concept_id="c1",
            error_type="article",
            count=3,
            examples=[
                {"original": "ein Hund", "corrected": "einen Hund"},
                {"original": "ein Auto", "corrected": "einen Auto"},
            ],
        )
        assert len(pattern.examples) == 2
        assert pattern.count == 3
