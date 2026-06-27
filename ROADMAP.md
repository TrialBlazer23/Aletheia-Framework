# Aletheia — The Real Build Roadmap

**Purpose:** This is the *practical* roadmap we actually follow to build Aletheia, the way it was designed. It replaces the theoretical corporate timeline in [`IMPLEMENTATION_ROADMAP.md`](IMPLEMENTATION_ROADMAP.md) (which assumes a 12–15 person team and a ~$3M budget) with a plan scoped for how this project is *really* being built: **by Claude (the engineer) working with the project owner (the designer, who does not code).**

> Read this together with [`CLAUDE.md`](CLAUDE.md), which is the canonical, faithful description of the design. This roadmap says *what we build and in what order*. CLAUDE.md says *what the thing must be*.

---

## The three rules this roadmap obeys

1. **Faithful to the design, not to "best practice for its own sake."** The goal is *this* AI, the way it was designed — the Family, the Domino Cascade, the Synapse Protocol, the Philosopher, the Resonance Cycle. We simplify *infrastructure* freely; we do **not** simplify away the *architecture*. (See "Faithfulness contract" in CLAUDE.md.)
2. **Runnable at every step.** Every milestone ends in something you can actually run with one command and watch work. No milestone is "a year of plumbing before anything happens." If you can't see it work, it isn't done.
3. **Glass Box from line one.** Every message between agents is logged to an auditable cascade log from Milestone 0. Transparency is the whole point of the project, so it is the first thing we build, not the last.

---

## Stack decisions (made for you, with rationale)

The original docs specify an enterprise stack (RabbitMQ, PostgreSQL, Pinecone, Neo4j, Kubernetes-scale ops). That is correct *eventually*, but it is unrunnable for a solo non-coder owner and would stall us for months in infrastructure before a single agent talks. So for the build phase we use a **"runs on one machine with `python main.py`"** stack, behind clean interfaces so we can upgrade to the enterprise stack later **without rewriting the agents.**

| Concern | Design's eventual target | What we build first | Why | Upgrade path |
|---|---|---|---|---|
| Language | Python 3.10+ | **Python 3.11+** | As designed; best LLM ecosystem | — |
| Event bus (Domino Cascade) | RabbitMQ / Redis | **In-process async bus** (`asyncio`) behind a `MessageBus` interface | Zero infra; the Synapse *semantics* are identical | Swap implementation for Redis/NATS; agents unchanged |
| LLM | OpenAI / Anthropic / Ollama | **Anthropic Claude** by default, behind a provider interface | Strongest models today; one good default beats five half-wired ones | Add OpenAI / local Ollama as drop-in providers |
| Vector store | Pinecone / Weaviate | **Chroma** (embedded, local file) | No cloud account, no cost, no ops | Swap for Pinecone/Weaviate behind the same `VectorStore` interface |
| Knowledge graph | Neo4j | **NetworkX + SQLite** (then Kùzu, embedded) | Runs locally; no server | Neo4j behind the same `GraphStore` interface |
| Relational store / logs | PostgreSQL | **SQLite** | One file, zero setup | Postgres later |
| API / dashboard | FastAPI + Grafana | **CLI first**, tiny FastAPI status page when needed | See it work in the terminal before building UI | FastAPI + a real dashboard in hardening |
| Tracing | OpenTelemetry + Jaeger | **Our own cascade log (JSONL)** | The cascade log *is* the audit trail the design demands | Add OTel exporters later |

**The one principle behind this table:** every external dependency hides behind a small interface (`MessageBus`, `LLMProvider`, `VectorStore`, `GraphStore`). The agents only ever see the interface. That is what lets a non-coder owner run it today and a team scale it later without throwing work away.

---

## What we are building toward (the faithful target)

Six "Family" agents with their canonical UIDs, talking over the **Domino Cascade** (event bus) using the **Synapse Protocol** (EVENT / TRIGGER / STATE_CHANGE messages), each wrapped in a **Synapse Interface Layer** (a *Listener* and a *Broadcaster*), exchanging typed **SDR** data, governed by the **Philosopher** enforcing the **Prime Directives**, and improving itself through the supervised **Resonance Cycle** with a **Human Gavel**. Full detail lives in `CLAUDE.md`.

| Agent | UID | Built in |
|---|---|---|
| Nexus-Mind (Orchestrator) | `0x0001` | Milestone 1 |
| Archivist (Memory / ground truth) | `0x00A1` | Milestone 1, upgraded in 4 |
| Narrator (Interface / output) | `0x00B2` | Milestone 1 |
| Philosopher (Safety kernel) | `0x00C3` | Milestone 2 |
| Visionary (Simulation / creative) | `0x00D4` | Milestone 6 |
| Diagnostician (Self-healing) | `0x00E5` | Milestone 3 |

---

## The milestones

Each milestone is **independently demoable**. We do them in order; each one is a handful of focused build sessions, not weeks of calendar time. We don't move on until the "✅ Done when" demo actually runs.

### Milestone 0 — The Nervous System (Synapse core + Glass Box) — ✅ DONE
*Build the spine before the organs.*

- Repo/package scaffold (`aletheia/`), dependency setup, one-command run + test.
- **Synapse Protocol** as code: the message envelope exactly per NSAP-0001 — `Header` (`Message-ID`, `Source-UID`, `Timestamp`, `Message-Type`, `Protocol-Ver`) and the three `Body` shapes (EVENT / TRIGGER / STATE_CHANGE). UID helpers (`CATEGORY:TYPE:IDENTIFIER`).
- **Message bus**: in-process async pub/sub = the Domino Cascade backbone, behind a `MessageBus` interface.
- **Synapse Interface Layer (SIL)**: base classes for the *Listener* (`scanNetwork` → `filterRelevantMessages` via `InterestProfile.json` → `parsePayload` → `triggerParentModel`) and the *Broadcaster* (`receiveDataFromParent` → `packagePayload` → `constructEventMessage` → `broadcast`), plus the 4-step handshake (receive → **ACKNOWLEDGE** with a `STATE_CHANGE: TASK_ACCEPTED` → execute → broadcast `EVENT`).
- **Cascade Log**: append-only JSONL of every message — the auditable Glass Box record.
- A `FamilyMember` base agent that wires a Listener + Broadcaster together.

✅ **Done when:** two dummy agents complete a real TRIGGER → ACK → EVENT handshake over the bus, and the cascade log shows the full ordered flow. Tests green.

➡️ **Maps to design:** NSAP-0001 (Protocol), NSAP-0002 (Interface Layer), the Domino Cascade, the "auditable Glass Box."

---

### Milestone 1 — The First Living Cascade (3-agent MVP) — ✅ DONE
*Nexus-Mind → Archivist → Narrator, end to end.*

- `LLMProvider` interface; **Claude** default provider (config via env). Cost-safe defaults (cheap model for routine steps, strong model for reasoning).
- **SDR Tier-1 primitives** as typed models: `Metadata_Block`, `Text_Block`, `Confidence_Score`, `UID_Reference`, `Status_Code_Item` — plus minimal `Task_Definition` and `Knowledge_Graph_Element`.
- **Nexus-Mind** `0x0001`: parses the user request, plans with the LLM, emits a TRIGGER to the Archivist.
- **Archivist** `0x00A1` (v1): ingests a small corpus into Chroma, retrieves context, broadcasts `EVENT: DATA_VALIDATED` with a confidence score.
- **Narrator** `0x00B2`: synthesizes an answer from the retrieved context, broadcasts `EVENT: DRAFT_READY`.
- Nexus collects the result and returns it. A simple CLI console to talk to the system.
- **First use case: Aletheia answering questions about its own design** (we ingest this repo's docs). Self-referential, genuinely useful, and a great test.

✅ **Done when:** you type a question in the console, watch the cascade hop Nexus → Archivist → Narrator in the log, and get a grounded answer back.

➡️ **Maps to design:** The Family (3 of 6), Domino Cascade in motion, SDR payloads, the "separate generation from everything else" thesis.

---

### Milestone 2 — The Conscience (Philosopher + Prime Directives) — ✅ DONE
*Nothing reaches the user until the Philosopher approves it.*

- The **four Prime Directives** encoded as a machine-readable `prime_directives.yaml` (Sanctity of Information Flow, Cosmic Preservation, Transcendence of Flawed Motivation, Dynamic Equilibrium).
- **Philosopher** `0x00C3` (rule-based first, exactly as the design and ANALYSIS.md both recommend): PII / disallowed-content / bias checks + directive predicates. It sits on `DRAFT_READY`, holds **veto power**, and emits `EVENT: APPROVED` or `EVENT: REJECTED`.
- Every verdict is logged as an `SDR_Ethical_Analysis_Report` (principle cited, reasoning chain, confidence, escalation flag) — the audit trail the design requires.
- *Optional 2B:* an LLM-assisted Philosopher (Claude reasoning against the Directives) layered **on top of** the rule-based hard floor — never replacing it.

✅ **Done when:** a draft containing PII or a Directive violation is vetoed before it reaches you, and the rejection (with the cited Directive and reasoning) appears in the audit log.

➡️ **Maps to design:** The Philosopher as runtime safety kernel, Prime Directives, `SDR_Ethical_Analysis_Report`, defense-in-depth Layer 1+2.

---

### Milestone 3 — The Immune System (Diagnostician + observability)
*The system watches itself and heals.*

- **Diagnostician** `0x00E5`: monitors the bus, tracks every in-flight cascade by a correlation/choreography ID, detects loops and timeouts, emits `STATE_CHANGE` alerts, and trips a **circuit breaker** on runaway cascades.
- Produces `CHOREOGRAPHY_LOG` telemetry (the raw material the Resonance Cycle will later learn from).
- A lightweight live status view (CLI status, or a tiny FastAPI page) showing cascade health, agent latencies, and rejection rates.
- A **recovery cascade**: abort/restart a stuck cascade cleanly.

✅ **Done when:** we deliberately induce an infinite loop and a hung agent; the Diagnostician detects each, trips the breaker, logs the event, and the system stays alive.

➡️ **Maps to design:** The Diagnostician, self-healing, "System Harmony" monitoring, defense-in-depth Layer 3.

---

### Milestone 4 — Ground Truth (Knowledge-Graph Archivist)
*The anti-hallucination core the whole thesis rests on.*

- **Archivist v2**: spaCy (`en_core_web_lg`) dependency parsing → entities + relations → graph store (NetworkX/SQLite, then embedded Kùzu) behind a `GraphStore` interface. **Hybrid retrieval**: vector search + graph traversal, merged and ranked.
- `SDR_Knowledge_Graph_Element` and `SDR_Fact_Assertion` with full provenance + confidence — every claim cites its source.

✅ **Done when:** the system answers a *relational* question ("What does the Philosopher enforce?") by traversing the graph, and every fact in the answer is traceable to a source.

➡️ **Maps to design:** The Archivist's deterministic-parsing grounding (the neuro-symbolic heart), `SDR_Knowledge_Graph_Element`, "grounded memory, not vector vibes."

---

### Milestone 5 — Learning, Supervised (Resonance Cycle + Human Gavel)
*The heartbeat: the system turns its own failures into wisdom — with you holding the gavel.*

- **Performance analytics** over `CHOREOGRAPHY_LOG`s: Efficiency / Fidelity / Coordination / Alignment indices.
- **Resonance Engine** implementing the four phases: Dissonance Detection → Harmonic Analysis (root cause from the cascade log) → Proposal Generation (a `POLICY_UPDATE`) → Integration.
- **Safety gates, all of them, as designed:** the Philosopher simulates every proposed update in an isolated **Resonance Sandbox**; the change is rate-limited; a snapshot is taken for **rollback**; and nothing applies without the **Human Gavel** (a simple approval prompt/UI for you).
- Operational behavior lives in a versioned `operational_policy.json` that agents read at runtime.

✅ **Done when:** we replay the canonical RFC-001 failure (a satirical article ingested as fact); the system traces the root cause, proposes a policy patch, the Philosopher clears it in sandbox, you approve it via the gavel, behavior changes — and rollback restores the old behavior on command.

➡️ **Maps to design:** The Resonance Cycle (RFC-001), the Human Gavel, sandboxing, rate-limiting, rollback, "Level 2 learning."

---

### Milestone 6 — Expansion + Hardening (Visionary, then production-readiness)
*The sixth family member, and making it solid.*

- **Visionary** `0x00D4`: simulation / creative asset generation, bringing the creative SDR types online (scene, character, soundscape, color, music). Wired into creative cascades (e.g. the "concept art for a new creature" flow from the design docs).
- **Hardening / scale-up** (as needed): swap the in-process bus for Redis/NATS, SQLite → Postgres, message signing + auth, secrets management, packaging, and richer docs/examples.

✅ **Done when:** a creative cascade (Archivist → Narrator → Visionary) produces a generated asset end-to-end, fully audited; and the system can optionally run on the upgraded infrastructure without agent code changes.

➡️ **Maps to design:** The Visionary, creative SDR types, the full 6-agent Family, and the path to the enterprise stack in `IMPLEMENTATION_ROADMAP.md`.

---

## Design decisions & upgrades I'm making (the design is a year old)

You asked me to make it better and to upgrade what's outdated. Here's what I'm changing from the original docs and why — flag anything you disagree with:

1. **Default LLM = Claude (latest models), not GPT-3.5/4.** The docs predate current models. We use the strongest available models behind a provider interface, so you're never locked in.
2. **Local-first infrastructure** (in-process bus, Chroma, SQLite, NetworkX) instead of cloud services — so *you* can run the whole thing yourself today. The enterprise stack becomes an upgrade, not a prerequisite.
3. **Rule-based Philosopher before LLM-based** — both the design and the analysis agree, and it's the safe order. The LLM Philosopher layers on top, never replaces the deterministic floor.
4. **The Archivist keeps spaCy deterministic parsing** (it's the anti-hallucination thesis, non-negotiable) but we *augment* it with modern LLM structured-extraction, using spaCy as the grounding check. Best of both.
5. **Cascade Log is built first, not last.** Auditability is the product's reason to exist, so it's the foundation.
6. **Interfaces everywhere** (`MessageBus`, `LLMProvider`, `VectorStore`, `GraphStore`) so today's simple choices and tomorrow's enterprise choices coexist without rewrites.

---

## Decisions I need from you (no rush — I have sensible defaults)

These are the few choices that are genuinely yours, not mine. I'll proceed on the **recommended default** unless you say otherwise:

1. **LLM provider & cost.** Default: **Claude API** (costs a few dollars in testing, best quality). Alternative: **local Ollama** (free, private, but needs a capable computer and is lower quality). 
2. **First use case for the MVP.** Default: **Aletheia answers questions about its own design docs** (self-contained, no extra data needed, genuinely useful). We can switch to any domain you care about later.
3. **How autonomous the Resonance Cycle may ever get.** Default (and the design's stated stance): **Human Gavel forever** — every self-modification needs your approval. We can revisit only LOW-impact auto-updates much later, if ever.

---

## The immediate next step

**Milestone 0.** When you say go, I scaffold the repo and build the Synapse nervous system + Glass Box cascade log, and show you two agents completing a handshake over the bus. Everything else stands on that.
