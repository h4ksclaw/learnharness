# LearnHarness — Vision & Design Decisions

## The Problem

Every AI learning tool today is either:
- **A chatbot that gives answers** (ChatGPT, Claude) — no spaced repetition, no knowledge tracking, no adaptation
- **A flashcard app with spaced repetition** (Anki) — no conversation, no AI, no teaching intelligence
- **A gamified course** (Duolingo) — locked to one domain, no free conversation, AI features not integrated with the learning engine
- **A document Q&A tool** (NotebookLM) — no learning progression, no mastery model, no review scheduling

Nobody has combined conversational AI + knowledge tracing + spaced repetition + adaptive difficulty into a single open system.

## The Vision

A **learning harness** — a system that wraps any LLM in pedagogical intelligence and makes it a real tutor. Not a chatbot that happens to know facts, but a system that:

1. **Understands what you know** — maintains a per-concept mastery model updated from every interaction
2. **Corrects you naturally** — inline corrections on your messages, expandable for detail, never overwhelming
3. **Remembers over time** — schedules reviews using FSRS so knowledge doesn't decay
4. **Adapts** — difficulty, topics, and pacing shift based on your demonstrated competency
5. **Reaches out** — proactive heartbeat reminds you when material is due
6. **Is domain-agnostic** — works for German, Python, organic chemistry, music theory, anything

### Primary Use Case

The initial driver is **language learning — specifically German**. The system should feel like a German friend who:
- Only speaks German to you (immersion)
- Gently corrects your mistakes without breaking conversation flow
- Remembers what grammar/vocabulary you struggle with
- Brings up old material at the right intervals so you don't forget
- Gradually increases complexity as you improve

### Why Domain-Agnostic?

Because the architecture is the same whether you're learning German verb conjugation or Python list comprehensions. The LLM extracts concepts, the knowledge graph stores them, BKT tracks mastery, FSRS schedules reviews. The *content* changes but the *machinery* doesn't.

An agent is just a system prompt + rules + domain. "You teach German, respond only in German" is one agent. "You teach Python, use Socratic method" is another. The platform doesn't care — it's the same engine underneath.

This is the "custom bot creator" model: users create agents, give them a master prompt, and the learning harness handles the rest.

---

## Key Design Decisions

### D1: Backend-first, API-driven

**Decision**: The backend IS the product. Frontends are thin clients.

**Why**: 
- The learning intelligence (FSRS, BKT, concept extraction) must live in one place
- Any frontend should work: web UI, IRC bot, Telegram, Flutter, CLI
- The API is OpenAI-compatible so existing chat clients work transparently
- Avoids coupling learning logic to any UI framework

**Alternative considered**: Monolithic app with built-in UI (like OpenTutor). Rejected because it locks the learning engine to one interface and makes alternative frontends second-class citizens.

### D2: PostgreSQL + pgvector (not Neo4j)

**Decision**: Use Postgres with pgvector for both relational data and vector similarity search. Concept relationships stored as adjacency-list tables.

**Why**:
- One database service, not two
- pgvector handles semantic search well enough for MVP scale
- Recursive CTEs can traverse the concept graph for prerequisite queries
- No extra infrastructure (Neo4j requires a separate service + license awareness)

**When to reconsider**: If multi-hop graph queries become a bottleneck at scale, Apache AGE (Postgres extension) or migration to Neo4j is the path. The schema is designed to make this swap straightforward.

### D3: FSRS for spaced repetition

**Decision**: Use the Free Spaced Repetition Scheduler (FSRS v4.5+) via `py-fsrs`.

**Why**:
- Neural network-based, trained on millions of review logs
- 30-50% fewer reviews than SM-2 for the same retention
- Default in Anki 23.10+ — battle-tested by millions of users
- Open-source, MIT-licensed, available in Python and TypeScript

**Alternative considered**: Custom LLM-enhanced scheduling (LECTOR-style). Too early — LECTOR is a 2025 paper, no production implementations. FSRS is proven. LLM-enhanced scheduling is a future enhancement.

### D4: BKT for knowledge tracing

**Decision**: Bayesian Knowledge Tracing for per-concept mastery estimation, with soft updates from LLM conversational inference.

**Why**:
- BKT is simple, interpretable, and proven since 1995
- Four parameters (prior, slip, guess, transit) per concept
- Works with both hard observations (quiz correct/incorrect) and soft signals (LLM estimates mastery from chat)
- The LLM analyzes each message and emits a 0-1 confidence that the learner knows each concept — BKT updates smoothly from this

**Future**: DKT/AKT (deep knowledge tracing with neural networks) could improve accuracy. The interface is designed so the tracing backend is swappable.

### D5: LLM-powered knowledge graph (auto-constructed)

**Decision**: The LLM extracts concepts, relationships, and corrections from every chat message. The graph builds itself dynamically.

**Why**:
- Domain-agnostic — no need to pre-define a concept taxonomy
- The LLM is already analyzing the message for the chat response
- Works for any subject: the LLM knows what "concepts" are in German grammar, Python syntax, or organic chemistry
- Concepts are embedded (pgvector) for semantic search — "show me everything related to verb conjugation"

**How**: Each user message goes through an analysis pipeline:
```
user message → LLM extracts → {concepts, edges, corrections, mastery_signals}
→ concepts upserted into DB → edges added → mastery updated via BKT → errors recorded
```

### D6: Agent persona system (not hardcoded tutors)

**Decision**: Tutors are defined by a persona configuration — system prompt, domain, language rules, teaching style, level.

**Why**:
- Creating a new tutor is just creating a new agent config
- Pre-built presets (german_tutor, python_mentor, etc.) for one-click setup
- Users can create custom agents with their own "master prompt"
- Per-agent LLM model override (use a big model for complex subjects, small model for simple chat)
- The learning engine doesn't change — only the system prompt does

### D7: Single-user deployment (for now)

**Decision**: Optimize for personal instance deployment (like Hermes, not like Duolingo).

**Why**:
- Reduces complexity: no auth system, no multi-tenancy, no rate limiting
- Aligns with self-hosted ethos
- The data model supports multi-user (learner_id everywhere) but we don't build the machinery for it yet
- Multi-user can be layered on later without breaking the architecture

### D8: OpenAI-compatible API

**Decision**: The main chat endpoint mirrors `POST /v1/chat/completions` with extension fields.

**Why**:
- Any OpenAI-compatible client works out of the box (LibreChat, Open WebUI, ChatBox)
- The learning extensions (corrections, mastery_deltas) are additive — standard clients just see text responses
- Rich clients can opt into the extension fields for inline corrections and progress widgets

### D9: MIT License

**Decision**: MIT, maximally permissive.

**Why**: Maximum adoption. No copyleft restrictions. Anyone can fork, build on, commercialize. The goal is to be the open-source standard for adaptive learning.

### D10: Default web UI, open to all frontends

**Decision**: Build a management web UI (agent creation, learner dashboard, chat with corrections) as the default frontend, but design the API so any client type is a first-class citizen.

**Why**:
- Web UI is needed for management (create agents, view graphs, configure settings)
- But the chat experience should be available everywhere — IRC, Telegram, mobile
- Like Hermes or OpenClaw: a management shell + multi-channel delivery
- The API response envelope carries rich data; each frontend renders at its own fidelity

---

## What This Is Not

- **Not a Duolingo clone** — no locked skill trees, no gamification as primary driver, no limited domains
- **Not a chatbot wrapper** — the learning intelligence is the core, the LLM is just one component
- **Not an LMS** — no course authoring, no SCORM compliance, no institutional features
- **Not a flashcard app** — flashcards are a side effect of the review system, not the primary interface

## Inspiration & Prior Art

- **Duolingo** — proved adaptive learning + spaced repetition + AI conversation works at scale (500M users). But: locked to languages, AI not integrated with knowledge model, closed-source.
- **Khanmigo** — best Socratic AI tutoring pedagogy. But: not integrated with Khan Academy's mastery system in real-time.
- **ALEKS** — Knowledge Space Theory, prerequisite-aware adaptive assessment. But: closed, expensive, math/science only.
- **Anki + FSRS** — gold standard spaced repetition. But: zero AI, zero conversation.
- **OpenTutor** — closest open-source project (FSRS + BKT + knowledge graph + LLM). But: workspace UI, not chat-first.
- **Hermes** — architecture inspiration for multi-channel, single-user, self-hosted agent platform.

---

## Success Criteria

For the primary use case (learning German):
1. I can chat in German and get corrected naturally
2. The system remembers my weak spots and tests them later
3. I can see my progress on a knowledge graph
4. The system proactively reminds me to review overdue material
5. It works entirely locally with Ollama (no API costs)
6. I can also use it for any other subject by creating a new agent
