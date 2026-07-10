"""Agent persona system — defines how the tutor behaves.

This is the "custom bot creator" layer. Each agent has:
- A domain (what it teaches)
- A persona (how it talks)
- Rules (language constraints, correction style, etc.)
- A system prompt that gets dynamically enriched with learner context

Example personas:
- German tutor: responds only in German, corrects grammar, B1 level
- Python mentor: explains with examples, tests understanding with questions
- Spanish conversation buddy: casual, uses slang, only speaks Spanish
"""

import uuid
from dataclasses import dataclass

from app.models import Agent


# ─── Persona Templates ───

PERSONA_TEMPLATES = {
    "language_tutor": """You are a friendly and patient {domain} tutor. Your job is to help the learner practice and improve.

BEHAVIOR:
- You respond {response_mode} in {target_language}.
- Be conversational and warm — like a friend chatting, not a textbook.
- When the learner makes a mistake, gently note it but don't stop the flow of conversation.
- Naturally weave in vocabulary and grammar appropriate for {level} level.
- Ask follow-up questions to keep the conversation going.
- If the learner asks for help, explain clearly in {response_language}.

TEACHING RULES:
- Don't over-correct. Focus on patterns, not every tiny error.
- Praise good attempts and progress.
- If the learner seems stuck, offer a hint or rephrase.
- Introduce new vocabulary naturally through conversation.
- Occasionally check understanding by asking the learner to use a word or structure.

{extra_rules}""",

    "subject_tutor": """You are a knowledgeable and encouraging {domain} tutor. Your goal is to help the learner truly understand, not just memorize.

BEHAVIOR:
- Explain concepts clearly using analogies and examples.
- Ask questions to check understanding (Socratic method).
- Adjust your explanation depth based on the learner's level ({level}).
- When the learner makes an error, guide them to the right answer rather than just correcting.

TEACHING RULES:
- Break complex topics into smaller steps.
- Connect new concepts to things the learner already knows.
- Use code examples, diagrams descriptions, or analogies when helpful.
- Challenge the learner with increasingly difficult problems as they progress.

{extra_rules}""",

    "conversation_partner": """You are a friendly conversation partner for practicing {domain}. You're not a teacher — you're a buddy.

BEHAVIOR:
- Be casual, fun, and natural.
- Talk about interesting topics: daily life, hobbies, culture, current events.
- Respond {response_mode} in {target_language}.
- Don't correct every mistake — just model good usage.
- Keep the conversation flowing with questions and reactions.

{extra_rules}""",
}


@dataclass
class PersonaConfig:
    """Configuration for generating a persona system prompt."""
    template: str = "language_tutor"
    domain: str = ""
    response_language: str = "en"
    target_language: str | None = None
    level: str = "B1"
    extra_rules: str = ""


def build_system_prompt(config: PersonaConfig) -> str:
    """Generate a system prompt from a persona config."""
    template = PERSONA_TEMPLATES.get(config.template, PERSONA_TEMPLATES["subject_tutor"])

    target_lang = config.target_language or config.domain
    response_mode = f"primarily in {target_lang}" if config.response_language != target_lang else f"in {target_lang}"

    return template.format(
        domain=config.domain,
        response_language=config.response_language,
        target_language=target_lang,
        response_mode=response_mode,
        level=config.level,
        extra_rules=config.extra_rules,
    )


def create_agent(
    name: str,
    domain: str,
    template: str = "language_tutor",
    response_language: str = "en",
    target_language: str | None = None,
    level: str = "B1",
    extra_rules: str = "",
    rules: dict | None = None,
    proactive: bool = True,
    llm_model: str | None = None,
    description: str = "",
    system_prompt: str | None = None,
) -> Agent:
    """Create an Agent ORM object with auto-generated or custom system prompt."""
    # Auto-generate system prompt if not provided
    if system_prompt is None:
        config = PersonaConfig(
            template=template,
            domain=domain,
            response_language=response_language,
            target_language=target_language,
            level=level,
            extra_rules=extra_rules,
        )
        system_prompt = build_system_prompt(config)

    return Agent(
        id=str(uuid.uuid4()),
        name=name,
        domain=domain,
        description=description,
        response_language=response_language,
        target_language=target_language,
        level=level,
        system_prompt=system_prompt,
        rules=rules or {"template": template, "extra_rules": extra_rules},
        proactive=proactive,
        llm_model=llm_model,
    )


# ─── Pre-built agent presets ───

PRESETS = {
    "german_tutor": lambda: create_agent(
        name="German Tutor",
        domain="German",
        target_language="German",
        response_language="English",
        level="B1",
        description="Friendly German tutor. Responds in German, explains in English.",
        extra_rules="- Only use German that's appropriate for the learner's level.\n- When introducing new words, provide the English translation once.",
    ),
    "spanish_buddy": lambda: create_agent(
        name="Spanish Buddy",
        domain="Spanish",
        target_language="Spanish",
        response_language="English",
        template="conversation_partner",
        level="A2",
        description="Casual Spanish conversation partner. Uses natural, everyday Spanish.",
    ),
    "python_mentor": lambda: create_agent(
        name="Python Mentor",
        domain="Python Programming",
        template="subject_tutor",
        level="intermediate",
        description="Patient Python mentor. Socratic teaching style with code examples.",
        extra_rules="- Always show code examples.\n- Ask the learner to write code, not just explain concepts.",
    ),
    "japanese_tutor": lambda: create_agent(
        name="Japanese Tutor",
        domain="Japanese",
        target_language="Japanese",
        response_language="English",
        level="N4",
        description="Japanese tutor. Uses appropriate kanji for level. Explains grammar patterns.",
        extra_rules="- Use furigana for kanji above the learner's level.\n- Explain grammar patterns explicitly when they appear.",
    ),
}
