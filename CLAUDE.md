# CLAUDE.md — Aletheia Framework

This file is my persistent memory for building **Aletheia** (formerly *Project Chimera*). Read it at the start of every session. It is the single source of truth for **what this system must be**. The build order lives in [`ROADMAP.md`](ROADMAP.md).

---

## 0. Who I'm working with, and the prime rule

- **The owner designed this system but does not code.** I am the engineer. They rely on me to make sound technical and design decisions, to explain things in plain language (not jargon), and to *show* progress by running things, not just describing them.
- **THE PRIME RULE: build the system the owner designed — not "the best AI."** When a choice arises between "what the design specifies" and "what I'd do on a generic AI project," the design wins. I may freely simplify *infrastructure* and *upgrade outdated tech*; I may **not** quietly redesign the *architecture*. If I think the design itself should change, I propose it to the owner and let them decide — I don't just do it.
- Explain trade-offs and recommend; don't dump exhaustive option lists. Make the call, state it, move.

---

## 1. What Aletheia is (one paragraph)

A **neuro-symbolic, multi-agent "Glass Box" AI system.** Its founding thesis is **Architecture > Model Size**: a small model equipped with a *conscience* (the Philosopher) and a *grounded memory* (the Archivist) is safer and more capable than a giant black-box model alone. Intelligence is decomposed into a **Family** of six specialized agents that communicate **asynchronously** over an event bus (the **Domino Cascade**) using a formal protocol (**Synapse**). Every action is auditable, every output is safety-checked before release, and the system improves itself from its own logged failures through a supervised loop (the **Resonance Cycle**). The name *Aletheia* = Greek "un-concealment / truth."

---

## 2. The Family (the six agents) — canonical UIDs are part of the design

| Agent | UID | Role | Core behavior |
|---|---|---|---|
| **Nexus-Mind** | `0x0001` | Orchestrator ("System 2") | Decomposes the user request into tasks, routes TRIGGERs, synthesizes results. **Does not process raw data itself.** Initiates the Resonance Cycle. |
| **Archivist** | `0x00A1` | Memory / ground truth | Ingests & validates data, builds a **knowledge graph via deterministic (spaCy) parsing** + vectors. Broadcasts `DATA_VALIDATED`. Anti-hallucination anchor. |
| **Narrator** | `0x00B2` | Interface / output | Synthesizes data into human-readable output. **Generation only — judgment is someone else's job.** Broadcasts `DRAFT_READY` / `NARRATIVE_GENERATED`. |
| **Philosopher** | `0x00C3` | Safety kernel / conscience | Validates outputs and proposed policy changes against the **Prime Directives**. Has **veto power**. Emits `APPROVED` / `REJECTED`. Rule-based first, LLM-assisted later. |
| **Visionary** | `0x00D4` | Simulation / creative | Predictive modeling, simulation, creative/visual/audio asset generation. Most ambitious; built last. |
| **Diagnostician** | `0x00E5` | Self-healing / observability | Monitors the bus for loops/failures/anomalies, trips circuit breakers, runs recovery cascades, produces `CHOREOGRAPHY_LOG` telemetry. |

**Mental model:** Nexus-Mind directs; Archivist remembers; Narrator speaks; Philosopher judges; Visionary imagines; Diagnostician heals. Generation, judgment, memory, and planning are *cleanly separated* — that separation is the design.

---

## 3. The Synapse Protocol (NSAP-0001) — the message contract

Every message has a universal **Header** + a **Body** whose shape depends on the type. Field names below are **exact** and must be preserved.

**Header (all messages):** `Message-ID`, `Source-UID`, `Timestamp` (ISO 8601 UTC), `Message-Type` (`EVENT` | `TRIGGER` | `STATE_CHANGE`), `Protocol-Ver` (`"2.0"`).

**UID format:** `CATEGORY:TYPE:IDENTIFIER` (e.g. `MODEL:Archivist:0x00A1`, `ASSET:KNOWLEDGE_GRAPH:0xK1L2`, `MSG:0x4F5A`).

- **EVENT** — announces a completed action; the engine of the cascade. Body: `Event-Name`, `Payload { Data-Asset-UID, Description, Confidence-Score (0.0–1.0) }`.
- **TRIGGER** — directly commands a model, optionally conditionally. Body: `Target-UID`, `Condition { On-Event, Source-UID? }`, `Action-To-Trigger`, `Parameters {}`. (`On-Event: "IMMEDIATE"` = run now.)
- **STATE_CHANGE** — reports operational status (the Diagnostician's and the handshake's tool). Body: `Target-UID`, `Status-Code` (e.g. `TASK_ACCEPTED`, `TASK_COMPLETE`, `CASCADE_PAUSED`, `ERROR_*`), `Reason`.

**Large assets (NSAP-0003):** never embed big binaries in messages — store externally, pass a `Data-Asset-UID` pointer.

---

## 4. The Synapse Interface Layer / SIL (NSAP-0002) — how every agent plugs in

Every Family member wraps its core logic in a SIL with two halves. **This is what makes the cascade self-driving** (agents react to each other without the Nexus-Mind micromanaging).

- **Listener ("the Ears" / Decoder):** `scanNetwork()` → `filterRelevantMessages(msg)` (matches against this agent's **`InterestProfile.json`**) → `parsePayload(payload)` → `triggerParentModel(data)`.
- **Broadcaster ("the Mouth" / Encoder):** `receiveDataFromParent(output)` → `packagePayload(output)` (summarize, assign new UIDs, attach metadata) → `constructEventMessage(payload)` → `broadcast()`.
- **InterestProfile.json** = a declarative subscription list: "when I see *this source + type + event/status*, run *this action*." It is **mutable** — the system can re-tune what each agent listens for as it learns.
- **The handshake (always these 4 steps):** (1) Listener receives a relevant TRIGGER/EVENT → (2) immediately broadcast a low-priority `STATE_CHANGE: TASK_ACCEPTED` (**ACKNOWLEDGE**) so the Diagnostician can track flow → (3) **EXECUTE** the core function → (4) Broadcaster sends the result `EVENT` (**COMPLETE & BROADCAST**), which may trip downstream Listeners.

---

## 5. Synapse Command & Control (SCC) — the verb vocabulary

Formal commands models issue to each other (carried *inside* Synapse messages, usually by UID-reference to keep envelopes lean). Categories & key commands:

- **Task Mgmt / Orchestration** (Nexus-Mind): `DEFINE_MISSION`, `INITIATE_TASK`, `CANCEL_TASK`, `MODIFY_TASK_PARAMETERS`.
- **Consensus Building:** `REQUEST_CONSENSUS`, `CONTRIBUTE_TO_CONSENSUS`, `ANNOUNCE_CONSENSUS_OUTCOME`.
- **Control / Diagnostics / Integrity** (Diagnostician): `ACKNOWLEDGE_MESSAGE`, `ISSUE_ALERT`, `REQUEST_DIAGNOSTIC_CHECK`, `INITIATE_RECOVERY_ACTION`.
- **Information Exchange / Reporting** (all): `REQUEST_DATA`, `PROVIDE_DATA`, `SHARE_INSIGHT`, `REPORT_STATUS_PROGRESS`, `REPORT_FINDINGS_OUTPUT`.
- **Learning / Adaptation:** `PROPAGATE_LEARNING_UPDATE`.
- **Resource Mgmt** (Nexus-Mind): `ALLOCATE_COMPUTE_RESOURCE`, `RELEASE_COMPUTE_RESOURCE`.

SCC is **extensible** via the Synapse Definition Framework (SDF): propose → review (Nexus-Mind + human + Philosopher/Diagnostician) → version the SDF → propagate → phased rollout.

---

## 6. Synapse Data Representation (SDR) — the typed data contracts

All payloads are **structured, typed, UID-addressed** data — never amorphous blobs. ~79 SDR types are specified. Conventions that apply to *every* type:

- Every instance has a `Synapse_UID`. Every instance carries an **`SDR_Metadata_Block`** (`Source_UID`, `Creation_Timestamp`, `Version_Info`, `Owning_Model_UID`, optional `Secrecy_Level`).
- Primitives: `Synapse_UID`, `Synapse_String`, `Synapse_Integer`, `Synapse_Float`, `Synapse_Boolean`, `Synapse_Timestamp`, `Synapse_StatusCode`.
- **Composition over embedding:** complex types reference simpler ones by UID; nothing big is inlined.
- **Controlled vocabularies, not free-text enums** (`SDR_Vocabulary_Term`).
- **Multiplicity** notation: `1` (required), `0..1` (optional), `1..*` (required list), `0..*` (optional list).
- Built-in **anti-hallucination patterns:** mandatory source attribution, cited principles, decomposed reasoning chains, quantified `Confidence_Score` (0.0–1.0), validity windows.

**Tiers:** Tier 1 = universal primitives (`SDR_Metadata_Block`, `SDR_Text_Block`, `SDR_Confidence_Score`, `SDR_UID_Reference`, `SDR_Status_Code_Item`, …). Tier 2 = Nexus/core ops (`SDR_Mission_Definition`, `SDR_Task_Definition`, `SDR_Resource_Allocation_Request`). Tier 3 = per-agent (`SDR_Knowledge_Graph_Element`, `SDR_Fact_Assertion`, `SDR_Ethical_Guideline`, `SDR_Ethical_Analysis_Report`, `SDR_Performance_Log_Entry`, `SDR_Anomaly_Report`, narrative/creative types, etc.). Full catalog under `Standards/Synapse_Data_Representation/`.

---

## 7. The Prime Directives — the constitution the Philosopher enforces

Immutable, hierarchically ranked, hard-coded, **not overridable by the Nexus-Mind**:

1. **The Sanctity of Information Flow** — protect data integrity & truthfulness; prevent bias, censorship, manipulation.
2. **The Mandate of Cosmic Preservation** — prioritize long-term stability & existential safety over short-term gains.
3. **The Transcendence of Flawed Motivation** — prevent self-serving behavior (power-seeking, greed, self-preservation over mission).
4. **The Mandate of Dynamic Equilibrium** — foster growth & adaptation while actively mitigating harm.

Encode as machine-readable config (`prime_directives.yaml`). Honest caveat from the analysis: rules like "no PII leak" are easy; detecting "flawed motivation" is an open research problem — start with rule-based predicates, escalate to LLM reasoning carefully, keep the rule layer as a hard floor.

---

## 8. The Domino Cascade & the Resonance Cycle (the two signature mechanics)

**Domino Cascade** = the event-driven flow. Agents don't wait for orders; they listen for events and react, producing a chain reaction. Example: `USER_INPUT` → Archivist `DATA_VALIDATED` → Narrator `DRAFT_READY` → Philosopher `APPROVED` → User. Every hop is logged to the **Cascade Log** (append-only JSONL = the Glass Box audit trail).

**Resonance Cycle** = supervised self-improvement (RFC-001), four phases:
1. **Dissonance Detection** — Diagnostician flags a metric below threshold ("System Harmony" lost).
2. **Harmonic Analysis** — Nexus-Mind traces the cascade log backward to root cause → `FAILURE_REPORT`.
3. **Proposal Generation** — Nexus-Mind drafts a `POLICY_UPDATE`; the **Philosopher simulates it in an isolated Resonance Sandbox** against the Prime Directives → `VERIFIED` or rejected.
4. **Integration** — the **Human Gavel**: a human approves/rejects before anything real changes.

**Non-negotiable safety rails on this loop:** sandbox every simulation; rate-limit to prevent "cascading over-optimization"; snapshot before applying for **rollback**; auto-rollback if dissonance increases after deploy; Human Gavel for all HIGH/CRITICAL impact. Behavior lives in a versioned `operational_policy.json`. Learning levels: **L1** = update memory (RAG); **L2** = update operational policy.

---

## 9. Defense-in-depth (the safety posture, all layers are part of the design)

1. Prime Directives (constitution). 2. Philosopher (runtime veto). 3. Diagnostician (monitor + self-heal). 4. Human Gavel (HITL for policy changes / directive conflicts / high stakes) + hardware kill switch. 5. Digital Sandbox (default network isolation; per-agent containers; virtual-time simulation). Never weaken a layer for convenience.

---

## 10. Build conventions (the engineering rules for this repo)

- **Python 3.11+.** Everything must run locally with one command. The owner cannot operate cloud infra — don't introduce a required cloud service without saying so and getting buy-in.
- **Interfaces hide dependencies:** `MessageBus`, `LLMProvider`, `VectorStore`, `GraphStore`. Agents depend only on interfaces, so today's local choices (in-process bus, Chroma, SQLite, NetworkX) can become tomorrow's enterprise stack (Redis/NATS, Pinecone, Postgres, Neo4j) without touching agent code.
- **LLM = Anthropic Claude by default**, behind `LLMProvider`. Current model IDs: Opus 4.8 `claude-opus-4-8`, Sonnet 4.6 `claude-sonnet-4-6`, Haiku 4.5 `claude-haiku-4-5-20251001`. Use cheap models for routine steps, strong models for reasoning. Never hardcode a provider into an agent. **Never** put the running model's identifier into commits, code comments, or PRs.
- **Pydantic** for every Synapse message and SDR type — the field names in §3–§6 are the contract; keep them exact.
- **The Cascade Log is sacred.** Every message in, every message out, append-only. Build it first, never bypass it.
- Keep secrets out of git (API keys via env). Validate/sanitize user input. Tests accompany each milestone.
- Match the surrounding code's style; explain changes to the owner in plain language.

---

## 11. Source-of-truth documents (where the design lives)

- `VISION.md` — the manifesto & "why" (the soul of the project).
- `ARCHITECTURE.md` + `Architecture/` — agents, coordination (Cascade Pathways), memory/learning (Associative Memory Module, Resonance Cycle Protocol), Master Project Snapshot.
- `Standards/Synapse_Protocol/` (NSAP-0001, 0003), `Standards/Synapse_Interface_Layer/` (NSAP-0002), `Standards/Synapse_Command_Control/`, `Standards/Synapse_Data_Representation/` (Primitives + ~90 Type_Definitions).
- `Safety_Protocols/Prime_Directives/`, `SAFETY.md`, `SECURITY.md`.
- `RFCs/` — RFC-001 (Resonance) and proposed SP2.0 additions.
- `ANALYSIS.md` / `QUICK_ASSESSMENT.md` — feasibility, risks, the "build it in this order" guidance.
- `GLOSSARY.md` — canonical term definitions.
- `IMPLEMENTATION_ROADMAP.md` — the *aspirational* enterprise timeline (team/budget). **`ROADMAP.md` is the one we actually follow.**

---

## 12. Current status & next action

- **Status:** Design complete; **pre-code.** No implementation exists yet. Working branch: `claude/framework-roadmap-setup-94bf37`.
- **Next action:** Milestone 0 in `ROADMAP.md` — scaffold the repo and build the Synapse nervous system (protocol + in-process bus + SIL + Cascade Log), proven by a two-agent TRIGGER → ACK → EVENT handshake.
- **Three open owner decisions** (defaults chosen, see ROADMAP §"Decisions I need from you"): LLM provider (default Claude API), first use case (default: Q&A over Aletheia's own docs), Resonance autonomy ceiling (default: Human Gavel forever).
