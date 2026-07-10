# LearnHarness — Vision & Design Decisions

## The Problem

Every AI learning tool today is either:
- **A chatbot that gives answers** (ChatGPT, Claude) — no spaced repetition, no knowledge tracking
- **A flashcard app** (Anki) — no conversation, no AI, no teaching intelligence
- **A gamified course** (Duolingo) — locked to one domain, AI not integrated with learning engine
- **A document Q&A tool** (NotebookLM) — no learning progression, no mastery model

Nobody has combined conversational AI + knowledge tracing + spaced repetition + adaptive difficulty + tools into a single open, domain-agnostic system.

## The Vision

A **learning harness** — a system where you create an AI agent with a master prompt, and it becomes a tutor that:

1. **Understands what you know** — maintains a per-concept mastery model updated from every interaction
2. **Corrects you naturally** — inline corrections, expandable for detail, never overwhelming
3. **Remembers over time** — schedules reviews using FSRS so knowledge doesn't decay
4. **Adapts** — difficulty, topics, and pacing shift based on demonstrated competency
5. **Reaches out** — proactive heartbeat reminds you when material is due
6. **Has tools** — can search the web, browse URLs, read papers, look up Wikipedia to build its knowledge
7. **Is domain-agnostic** — the agent's master prompt defines what it teaches. German, Python, chemistry, anything.

### How You Use It

1. Create an agent: give it a master prompt ("You are a German tutor, respond only in German")
2. Configure tools (web_search, wikipedia, arxiv) and channels (IRC, Telegram, web)
3. Set heartbeat frequency
4. Start chatting — the agent builds a knowledge graph, tracks your mastery, schedules reviews
5. The agent proactively reaches out when reviews are due or you've been inactive

The agent is generic. The master prompt makes it specific. The harness handles everything else.

---

## Key Design Decisions

### D1: Backend-first, API-driven, Docker-managed

**Decision**: Everything runs in Docker. The backend IS the product. Frontends are thin clients.

**Why**: Learning intelligence must live in one place. Any frontend connects via the API. Docker makes setup automatic — `docker compose up -d` and everything works.

### D2: Agent = master prompt + tools + channels

**Decision**: Agents have zero hardcoded domain/language fields. The master prompt IS the configuration.

**Why**: Maximum flexibility. "You teach German" is a prompt, not a schema field. "You teach Python with Socratic method" is a prompt. The platform doesn't care — same engine underneath.

### D3: PostgreSQL + pgvector

**Decision**: One database for relational data + vector similarity search.

**Why**: No extra services. pgvector handles semantic search. Recursive CTEs traverse the concept graph.

### D4: FSRS for spaced repetition

**Decision**: Free Spaced Repetition Scheduler via py-fsrs.

**Why**: Neural network-based, 30-50% fewer reviews than SM-2, default in Anki, battle-tested.

### D5: BKT for knowledge tracing

**Decision**: Bayesian Knowledge Tracing with soft updates from LLM conversational inference.

**Why**: Simple, interpretable, proven since 1995. The LLM analyzes each message and emits mastery confidence — BKT updates smoothly from this.

### D6: LLM-powered knowledge graph (auto-constructed)

**Decision**: The LLM extracts concepts, relationships, and corrections from every message. The graph builds itself.

**Why**: Domain-agnostic. Works for German grammar, Python syntax, or organic chemistry. The LLM knows what concepts are in any domain.

### D7: Tools system (agent can search the web)

**Decision**: Agents have pluggable tools — web_search, browse_url, wikipedia, arxiv.

**Why**: A tutor that can look things up is fundamentally more useful. The agent builds its knowledge base by researching, not just relying on pre-training.

### D8: Background heartbeat worker

**Decision**: Separate worker container runs the proactive scheduler.

**Why**: The agent initiates contact based on FSRS schedules, inactivity, and weak spots. This must happen in the background, not tied to API requests.

### D9: OpenAI-compatible API

**Decision**: Main chat endpoint mirrors POST /v1/chat/completions with extension fields.

**Why**: Any OpenAI-compatible client works out of the box. Learning extensions are additive.

### D10: Outbound message queue

**Decision**: Proactive messages written to outbound_messages table. Channel adapters poll and deliver.

**Why**: Decouples the learning engine from delivery. IRC bot, Telegram bot, web push all read from the same queue.

### D11: MIT License

Maximally permissive. Maximum adoption.

---

## What This Is Not

- Not a Duolingo clone — no locked skill trees, no gamification as primary driver
- Not a chatbot wrapper — the learning intelligence is the core, the LLM is one component
- Not an LMS — no course authoring, no SCORM, no institutional features
- Not a flashcard app — flashcards are a side effect of the review system

## Inspiration

- **Duolingo** — proved adaptive learning + SR + AI at scale. But closed, domain-locked.
- **Khanmigo** — best Socratic AI tutoring. But not integrated with mastery tracking.
- **Anki + FSRS** — gold standard SR. But zero conversation.
- **OpenTutor** — closest OSS (FSRS + BKT + KG). But workspace UI, not agent-driven.
- **Hermes** — architecture inspiration for multi-channel, self-hosted agent platform.
