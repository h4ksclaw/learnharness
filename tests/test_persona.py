"""Test the agent persona system."""

from app.agents.persona import build_system_prompt, PersonaConfig, create_agent


def test_language_tutor_prompt():
    config = PersonaConfig(
        template="language_tutor",
        domain="German",
        target_language="German",
        response_language="English",
        level="B1",
    )
    prompt = build_system_prompt(config)
    assert "German" in prompt
    assert "B1" in prompt
    assert "patient" in prompt.lower()


def test_subject_tutor_prompt():
    config = PersonaConfig(
        template="subject_tutor",
        domain="Python Programming",
        level="intermediate",
    )
    prompt = build_system_prompt(config)
    assert "Python" in prompt
    assert "Socratic" in prompt


def test_create_agent_generates_id_and_prompt():
    agent = create_agent(
        name="Test Tutor",
        domain="French",
        target_language="French",
        response_language="English",
    )
    assert agent.id  # uuid generated
    assert "French" in agent.system_prompt
    assert agent.proactive is True


def test_custom_system_prompt_preserved():
    agent = create_agent(
        name="Custom",
        domain="Math",
        system_prompt="You are a math wizard.",
    )
    assert agent.system_prompt == "You are a math wizard."


def test_presets_available():
    from app.agents.persona import PRESETS
    assert "german_tutor" in PRESETS
    assert "python_mentor" in PRESETS

    agent = PRESETS["python_mentor"]()
    assert "Python" in agent.system_prompt
