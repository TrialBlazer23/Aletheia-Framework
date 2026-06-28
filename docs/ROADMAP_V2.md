# Aletheia — Project Review & v2 Roadmap

*Prepared for the owner by the lead engineer. Written in plain language; the technical detail is here when you want it, but every section opens with what it means for you.*

---

## 1. Executive summary

Aletheia is real and it runs. The six-agent Family is wired together over the event bus, a question or a creative brief flows through the whole Domino Cascade end to end, the Philosopher genuinely vetoes unsafe output before you ever see it, and the supervised learning loop (the Resonance Cycle) really does change behaviour and roll it back — all of it written to the append-only Glass Box log, and all of it proven by 110 passing tests. That is a genuine achievement: the *architecture* you designed — generation separated from judgment separated from memory separated from planning — holds in the code, not just on paper.

The honest qualifier is that what's complete is **one faithful vertical slice through each agent, not the full Synapse standard**. Several headline capabilities are present in spirit but simplified in substance: the Nexus-Mind doesn't yet *plan* (it runs one fixed pathway), the Philosopher enforces only one of the four Prime Directives at runtime (and via keyword rules, with no LLM layer yet), the "knowledge-graph traversal" is really a smart keyword scan over a real graph, and only about a quarter of the ~79 typed-data contracts are built. Nothing is faked or hidden — the code's own docstrings are candid — but the "M0–M6 complete / the Family is whole" framing describes *breadth of agents present*, not *depth of every specified feature*. This is a **faithful prototype**, not a production system, and the rest of this document holds that line: nowhere here is "production-grade," because nothing yet is (no CI, an editable audit log, no inter-agent auth).

The single most consequential gap is operational, not architectural: **there is no automated safety net** — no continuous integration runs those 110 tests on a change, the audit log can be edited without detection, agents trust each other's identity blindly, and the emergency stop has no button wired to it. v2 should be about turning this faithful prototype into a *trustworthy* system: hardening the safety and audit layers first, then deepening the agents that were staged down.

**The owner's standing defaults still hold and the roadmap respects them:** LLM provider = Claude API; first use case = Q&A over Aletheia's own docs; Resonance autonomy ceiling = Human Gavel forever. Two later milestones (M11's document-ingestion and M12's post-deploy monitoring) brush against the second and third of those, so they are surfaced as explicit owner decisions rather than assumed.

---

## 2. What's built today

**The six agents are all present and connected** (verified: `test_six_agents_are_connected` passes), each wrapped in a real Synapse Interface Layer (Listener + Broadcaster) reacting to events on its own — the self-driving cascade is authentic, not centrally puppeteered.

| Agent | What genuinely works today | Honest limit |
|---|---|---|
| **Nexus-Mind** `0x0001` | Coordinates a turn, awaits the Philosopher's verdict, returns the answer; never touches raw data (faithful) | Fires one fixed trigger — no task decomposition, planning, or synthesis |
| **Archivist** `0x00A1` | Dual ingestion (vectors **and** a real spaCy-built knowledge graph); hybrid retrieval; every fact cites its source; large assets stored by `Data-Asset-UID` pointer, never inlined (NSAP-0003 — verified in code and tests) | Graph lookup is a keyword scan, not multi-hop traversal; "vector" store is TF-IDF, not embeddings |
| **Narrator** `0x00B2` | Grounded answer/concept generation; degrades gracefully with no LLM; never judges (faithful) | Narrative-craft features (story arc, dialogue) not built |
| **Philosopher** `0x00C3` | Real runtime veto over **both** Q&A and creative output; cites directive + redacted evidence | Rule-based only; enforces 1 of 4 directives at runtime; no LLM-assist layer |
| **Visionary** `0x00D4` | Produces structured creative briefs (visual/palette/soundscape/music) from a theme atlas; Philosopher judges its output too | Produces *briefs*, not generated images/audio; only visual art-direction is LLM-enriched |
| **Diagnostician** `0x00E5` | Passive whole-bus observer; loop detection + circuit-breaker containment work when exercised by tests/demo | Stall/timeout recovery is built but **never actually runs** on a live turn (no background sweep); kill-switch mechanism exists but is unwired |

**The five signature mechanics:** The **Domino Cascade** (event bus) and the **Synapse Protocol** envelope are high-fidelity — the exact hyphenated wire field names match the spec, verified by tests. The **Cascade Log** (Glass Box) records every message, append-only, before anything reacts — the "log first, then act" ordering is genuinely enforced. The **Resonance Cycle** is the most thoroughly built subsystem: all four phases, every safety rail (sandbox → Philosopher → rate-limit → snapshot → Human Gavel → auto-rollback), with the gavel defaulting to *deny* — though its snapshots are in-memory only (see §3, M5). **Defense-in-depth** holds *at the runtime-veto layer*: a PII leak is vetoed whether it comes from a Q&A answer or a creative package. (The deeper isolation layer — per-agent containers / network isolation — is notional today; see §4.)

**Run surface:** `python main.py` (console with `/create`, `/log`, `/health`, `/graph`, `/feedback`, `/policy`), `--web` (FastAPI browser UI; it **polls** for cascade state rather than streaming — relevant because M10 proposes a true streaming visualizer), and demo flags `--creative / --resonance / --knowledge / --diagnostics / --handshake`. Runs fully offline (no API key → graceful degradation) or live with Claude.

**Test state:** 110 tests, all passing in ~20s. The tests are *behavioural* — they assert real invariants (veto enforcement, rollback, wire field names), not smoke. Line coverage is high but **not measured by any tool in the repo, so no figure is claimed here.** And critically, **nothing runs these tests automatically.**

---

## 3. Completeness assessment (milestone by milestone)

Verdicts are from the adversarial "is the done-claim true?" verifications. *Confirmed* = the claim holds end-to-end. *Partial* = real but narrower than the words imply. *Overstated* = the claim outruns the code.

| Milestone | Verdict | One-line reason |
|---|---|---|
| **M0 — Synapse core + Glass Box** | **CONFIRMED** | Message envelope matches NSAP-0001 exactly; handshake and append-only log proven by tests; the spine is spec-faithful and well-tested. |
| **M1 — First living cascade (3 agents)** | **PARTIAL** | The cascade runs and returns grounded answers, but the Nexus-Mind "plans/decomposes/synthesizes" claim is overstated — it fires one fixed trigger and synthesizes nothing. |
| **M2 — Philosopher + Prime Directives** | **PARTIAL** | The veto is real and works; but only 1 of 4 directives is enforced at runtime, the PII rule is mis-filed under the wrong directive, and the promised LLM-assist layer does not exist (correctly deferred, but "constitution enforced" overstates it). |
| **M3 — Diagnostician + observability** | **PARTIAL** | Loop detection + circuit breaker genuinely contain a runaway *when exercised by tests/demo*, and are passive on healthy traffic (confirmed). But stall/timeout recovery is **never actuated on a live turn**, delivery-error handling is count-only, and the global kill-switch is unwired. |
| **M4 — Knowledge-Graph Archivist** | **PARTIAL** | Hybrid retrieval over a *real* spaCy-built graph with full provenance is genuine; "traversal" is overstated — it's a keyword-ranked scan of all edges, single-hop, and the actual traversal methods are dead code on the live path. |
| **M5 — Resonance Cycle + Human Gavel** | **PARTIAL** | Sandbox simulation, snapshot-before-apply, rollback, and gavel-default-deny all hold within a single process and are proven by the canonical satire scenario. But snapshots/audit are **in-memory only**, so **durable rollback is unproven — a self-modification cannot be undone after a process restart.** That is a correctness gap in the headline feature, not a footnote. |
| **M6a — Visionary + creative cascade** | **CONFIRMED (as scoped)** | The creative cascade runs end to end and the Philosopher vetoes unsafe creative output. Honestly scoped: the Visionary outputs *briefs*, not rendered assets — which the docs say. |
| **M6b — M6 hardening (bus/auth/secrets/packaging)** | **NOT STARTED** | None of the second-half hardening (Redis/NATS, Postgres, message signing/auth, secrets management, packaging) exists. The "M6 complete" label refers to M6a only. |

**Net:** **M0 stands up cleanly to scrutiny.** M5 is *mostly* sound — its in-process safety rails are real and well-proven — but durable rollback across restarts is unverified, so it is not a clean confirm. M1–M4 each have a real working slice but a headline word ("plans," "enforces the constitution," "self-heals," "traverses") that outruns the code. M6 splits cleanly: the creative cascade (M6a) is confirmed; the hardening (M6b) has not begun. None of this is dishonest — it's scope-staging — but it is exactly the gap v2 should close.

---

## 4. Missing pieces & gaps (by severity)

*"Faithful" = building something the design already specifies. "Net-new" = an addition you'd need to approve under the prime rule.*

### Critical — fix before this is a system you can trust

- **No automated safety net (CI).** Faithful. The 110 tests only run if a human remembers to run them. For a system whose entire selling point is auditable safety, having no automated gate that keeps the suite green on every change is the single biggest gap. `.github/` contains only `FUNDING.yml` (verified).
- **The audit log is tamper-*able*, not tamper-*evident*.** Faithful (closes a stated promise). The Cascade Log is "sacred, append-only" by convention only — plain JSON lines, no integrity chaining. Anyone can edit or delete a line silently. The Glass Box is only as trustworthy as the filesystem.
- **Agents trust each other's identity with zero verification.** Net-new (but design-aligned; listed as M6 hardening). A message's `Source-UID` is self-asserted. A forged `EVENT: APPROVED` claiming to come from the Philosopher would make the system release content that never passed the safety kernel — a direct bypass of the conscience.
- **The live Claude provider — the thing you'll actually run — has zero test coverage.** Faithful. Every LLM test uses a fake or the offline stub. The real message-construction path is unverified.

### High — real capability gaps against the design

- **The Nexus-Mind doesn't plan.** Faithful (it's the design's central agent, staged down). No task decomposition, no routing decisions, no synthesis — one identical pathway every turn. The "System 2 orchestrator" is currently a fixed dispatcher.
- **Three of four Prime Directives are unenforced at runtime.** Faithful. Only Directive 4 has rules; the others are decorative for normal output. The Philosopher cannot detect bias/manipulation (Directive 1), existential-risk reasoning (Directive 2), or power-seeking/self-preservation (Directive 3) today. Per CLAUDE.md §7, Directive 3 ("flawed motivation") is explicitly an *open research problem* — its full detection is not something v2 can honestly promise (see §6, M10 scope note).
- **Stall recovery never runs.** Faithful. The self-healing code for hung agents exists and is tested, but nothing calls it on a real turn — a genuinely hung cascade would sit forever.
- **The emergency stop has no button.** Faithful (completes a SAFETY.md layer). The global kill-switch *mechanism* exists in code (verified) but no command, endpoint, or signal triggers it. You cannot currently stop the system on demand. (Note: this is the *software* stop. The "hardware kill switch" in CLAUDE.md §9 is out of v2 scope — it has no meaning for a single local Python process and only becomes relevant if Aletheia ever runs on dedicated/remote hardware.)
- **Process/network isolation (Defense-in-depth Layer 5) is notional, not real.** Net-new (design-specified). The design calls for per-agent containers and default network isolation; today all six agents run in one process with no sandboxing. The only "sandbox" that exists is the *Resonance* simulation sandbox (a different thing). This is a named safety layer and should be stated plainly as unbuilt.
- **No input sanitization / prompt-injection defense.** Net-new (but serves Directive 1). User text and retrieved documents flow into the LLM ungated — and the project's own canonical failure (a satirical source treated as fact) is exactly this class of problem.

### Medium — fidelity and durability gaps

- **Rollback isn't durable across restarts.** Faithful. Snapshots live in memory; a self-modification made in one session can't be undone in the next. (This is the correctness caveat behind the M5 "PARTIAL" verdict.)
- **~70% of the typed-data (SDR) catalog is unbuilt** (~23 of ~79 types built — figures verified), and the implemented ones often use simplified field sets rather than the spec's exact field names. Faithful-ish — the design says keep SDR field names exact, so this is real drift, though defensible scope-staging.
- **Controlled vocabularies are bypassed in favour of free-text strings.** Faithful — and arguably *higher* than Medium, since SDR §6 makes controlled vocabularies (not free-text enums) a core data contract *and* an anti-hallucination feature. Status-codes and entity-types are currently free-text strings.
- **The whole formal command vocabulary (SCC) is bypassed.** Faithful. Agents use ad-hoc action strings; the specified verbs (`DEFINE_MISSION`, `REQUEST_CONSENSUS`, etc.) appear nowhere. No consensus mechanism, and the SDF (Synapse Definition Framework) extensibility process — which exists in the docs (verified) — is unimplemented.
- **Secrecy levels and validity windows are inert/missing.** Faithful. Both are claimed anti-hallucination/safety features; neither does anything — facts never expire, secrecy is never checked.
- **Auto-rollback isn't a live monitoring loop.** Faithful. It's a one-shot self-consistency check, not the Diagnostician watching real dissonance over subsequent turns as RFC-001 describes.

### Low — cleanup and consistency

- No coverage/lint/type-check tooling in the repo (a stale Codacy config points at an external service). `CONTRIBUTING.md` still says "Project Chimera." **A document mislabeled `NSAP-0003` actually contains an old project snapshot — a pure doc-naming cleanup; the *NSAP-0003 large-asset contract itself is implemented and tested* (assets are stored in the `AssetStore` and passed by `Data-Asset-UID` pointer — verified), so this is genuinely Low and not a buried gap.** The console REPL and three demo entrypoints have no tests. The "Chroma" named in your notes is actually TF-IDF.

---

## 5. Enhancement options (by theme)

*Each: my recommendation, rough effort (S/M/L/XL), value, faithful-vs-net-new, and **the v2 milestone it maps to** (or an explicit Deferred bucket — nothing silently disappears).*

**Security & hardening** — *the highest-value theme.*
- **Hash-chain the Cascade Log** (S, high, faithful) — **M7**. Makes the Glass Box tamper-evident. Note: changes the on-disk log format, so existing logs need a one-time migration — flagged as an owner-awareness decision in §"Decisions."
- **Sign & verify inter-agent messages** (L, high, net-new/aligned) — **M9**. Closes the forged-verdict hole; touches the envelope, so owner approval required.
- **Wire the kill-switch to `/halt` + a web button + a SIGINT handler** (S, high, faithful) — **M8**.
- **Input-sanitization floor before the LLM** (M, high, net-new/aligned) — **M11** (owner decision required; now in §"Decisions").
- **Redact secrets/PII before they hit the log** (S, medium, *design-touching*) — **M7**. This changes *what the sacred log records* (privacy vs. Glass-Box completeness), so it is an owner sign-off item, not a silent "faithful" change.
- **Per-agent process/network isolation (Layer 5)** (XL, medium, net-new) — **Deferred to a future v3**; only meaningful once agents run as separate processes (M12 infra path is the prerequisite). Flagged so it isn't forgotten.

**Scale & infra** — *all enabled by the existing interfaces, no agent rewrites.*
- **Config-driven component selection** (S, high, faithful) — **M12**.
- **Promote the AssetStore + CascadeLog to interfaces with a shared backend** (M, high, faithful) — **M12**.
- **Redis/NATS bus** (L, high, faithful) and **Postgres-backed policy/log store** (M, medium, faithful) — **M12 (owner-gated)**.
- **`docker-compose` one-command deploy** (M, high, faithful) — **M12**.
- **Embedding-backed vector store (Chroma)** (M, medium, faithful) — **M12**.

**Observability** — *mostly surfacing data that already exists.*
- **Show System Harmony + the four indices live, every turn** (S, high, faithful) — **M10**.
- **A consolidated `/dashboard` page** (S, high, faithful) and **live cascade visualizer via streaming** (M, high, faithful/aligned) — **M10**.
- **OpenTelemetry as an *optional, off-by-default* export adapter** (M, medium, net-new) — **Deferred** (owner decision; in §"Decisions"). The log stays canonical.

**LLM & evaluation**
- **Token/cost tracking per turn** (M, high, faithful) and **model routing** (Haiku routine / Opus reasoning) (M, high, faithful) — **M12**; these *prove* the "Architecture > Model Size" thesis.
- **Prompt caching** (S, high, infra — I can just do this) — **M12**. Biggest single cost win for docs-Q&A.
- **A golden-question eval harness** (M, high, faithful) and **a faithfulness/grounding score the Philosopher can veto on** (M, high, faithful) — **M10**.

**Product & use-cases**
- **Ingest your own folder of documents** (S, high, net-new) and **multi-format loaders (PDF/TXT/HTML)** (M, high, faithful) — **M11 (owner decision)**.
- **Citations drill-down UI** (M, high, faithful) — **M11**.
- **Conversation memory** (M, high, net-new) — **Deferred** (owner decision; in §"Decisions") — needs a careful design talk so chat history never becomes citable "fact."

**Learning & multi-agent**
- **Build L1 learning** (the memory-correction half of the design's L1/L2 split — only L2 exists) (L, high, faithful) — **M12**.
- **Broaden the policy levers** beyond "distrust a source" (M, high, faithful) — **M12**.
- **Implement the consensus verbs + adopt the SCC verb layer / SDF process** (L, medium, faithful) — **Deferred to v3** (explicit; see §6 "Named gaps deferred"). Assigned a home, not dropped.
- **Activate InterestProfile re-tuning** — a built-but-dormant mechanism (M, medium, faithful) — **Deferred to v3** (explicit).

**Dev experience**
- **CI (pytest on every push, offline, no key needed)** (S, high) — **M7**. Top priority of the whole list.
- **ruff lint/format** (S, high), **coverage reporting** (S, medium), **opt-in mypy** (M, medium — it already found one real bug), refresh `CONTRIBUTING.md` (S) — **M7**.

---

## 6. Recommended v2 roadmap

**v2 = "make the faithful prototype trustworthy, then deepen it."** Same three rules as the original roadmap: *faithful to the design; runnable at every step; Glass Box from line one.* Each milestone is independently demoable and builds only on itself plus earlier milestones.

**Authoritative sequence (one order, with dependencies):**
**M7 → M8 → M10 → M9 → M11 → M12a → M12b.**
- M7, M8, M10 are all faithful, mostly small, and need no architecture decision from you — build them first, in that order.
- **M9 (message signing) runs after your approval** — it changes the message envelope, so it's gated; it has no code dependency on M10, so it can slot in whenever you greenlight it.
- M11 depends on M7/M8 (trust + stop button in place) and on your document/use-case decision.
- M12 is split into **M12a (durability + L1 learning + monitoring — faithful)** and **M12b (optional infra scale-up — owner-gated)**.

The earlier draft's "run M7→M8→M10 first" is the *front* of this same sequence — there is no second, conflicting order.

---

### M7 — The Trustworthy Glass Box (audit integrity + the safety net)
**Goal:** Make the things the project already claims about safety and auditability *actually true and automatically enforced.*
**Builds on:** nothing (foundation).
**What gets built:**
- GitHub Actions CI running the 110 tests (offline, no API key) + ruff + coverage report, on every push/PR.
- Hash-chained, tamper-evident Cascade Log with a `verify()` pass (one-time migration of existing logs — owner-awareness item).
- Secret/PII redaction before write (owner sign-off item — changes what the log records).
- A real test for the live Anthropic provider (mocked SDK — no API spend).
- The QAResult/CreativeResult type bug fixed (mypy already flags it).

**Done-when demo:** Open a PR with a deliberately broken change → CI goes red and blocks it. Hand-edit a line in `cascade_log.jsonl` → `verify()` reports exactly which record was tampered. CI badge green on `main`.
**Faithful or net-new:** Faithful (CI/log-integrity serve stated conventions; the mock test serves "Claude is the default"). **Effort: M.**

---

### M8 — The Stop Button & the Watchful Immune System
**Goal:** Give you a real emergency stop, and make the Diagnostician's self-healing actually fire in production.
**Builds on:** M7 (interventions are logged into the now-tamper-evident log).
**What gets built:**
- `/halt` + `/resume` console commands, a web kill-switch endpoint, and a SIGINT/SIGTERM handler — all calling the existing global circuit breaker, all logged as audited interventions.
- A background sweep that actually runs stall/timeout detection on every real turn (currently dormant).
- The Diagnostician consumes delivery-errors and emits the `DELIVERY_ERROR` anomaly the docs promise. *(Dependency check: the delivery-error count plumbing already exists per §4 — M8 turns the count into an emitted anomaly; no earlier milestone needed.)*

**Done-when demo:** Type `/halt` mid-cascade → everything stops, the stop is in the log; `/resume` (with confirmation) brings it back. Deliberately hang an agent in a live run → the Diagnostician detects the stall, aborts and recovers it, without external prodding.
**Faithful or net-new:** Faithful — completes SAFETY.md Layer 4 (*software* stop; hardware stop explicitly out of scope, see §4) and the M3 self-healing claim. **Effort: M.**

---

### M10 — Honest Grounding (measured & enforced anti-hallucination)
**Goal:** Turn the anti-hallucination thesis from a structural claim into a measured, enforced property — and make Harmony visible.
**Builds on:** M7 (eval harness rides the CI built there).
**What gets built:**
- A grounding/faithfulness score on every answer (deterministic overlap floor + optional cheap LLM judge).
- The Philosopher gains a rule that flags/vetoes ungrounded claims, citing Directive 1, starting in **flag-mode**.
- Live System Harmony + the four indices surfaced per turn, on a `/dashboard` (and a real *streaming* cascade visualizer, replacing today's polling view).
- A golden-question eval harness wired into CI.

**Flag-mode → hard-reject transition (explicit acceptance criteria):** start in flag-mode; promote a directive-class to hard-reject only when, on the golden set, **false-positive rate ≤ 5% over ≥ 100 graded answers across two consecutive CI runs**, with no regression on the existing golden questions. Until that bar is met, ungrounded answers ship *flagged*, not blocked — this is the staged risk you're accepting (and decision 5 below confirms it).

**Scope note on the other directives:** M10 enforces **Directive 1 (truthfulness/grounding)** only. Directive 2 (existential safety) and Directive 3 (flawed motivation) get a *rule-floor predicate layer* (cheap, conservative checks) **but are explicitly NOT solved** — CLAUDE.md §7 names Directive-3 detection an open research problem, and v2 does not pretend otherwise. Full multi-directive enforcement is a named gap deferred beyond v2 (see below).

**Done-when demo:** Ask a grounded question → high faithfulness score shown. Force the model to over-reach → the answer is flagged with Directive 1 cited. Watch Harmony tick per turn on the dashboard; see CI fail if a retrieval change regresses the golden set.
**Faithful or net-new:** Faithful — Directive 1 is literally "truthfulness." **Effort: L.**

---

### M9 — Inter-Agent Trust (message signing) — *owner-gated*
**Goal:** Close the forged-verdict hole so "every output is safety-checked before release" can't be bypassed.
**Builds on:** M7 (quarantine events logged into the tamper-evident log). No dependency on M10 — can run any time after approval.
**What gets built:**
- Per-agent signing keys (injected like the API key); the Broadcaster signs, the bus verifies before delivery; unverifiable messages are quarantined and logged. A new optional `Signature` header field — the five canonical header names stay exact. Verify-optional mode first for backward-compatible logs.

**Done-when demo:** Inject a hand-forged `APPROVED` event claiming the Philosopher's UID → the bus rejects it, logs the attempt, and the unsafe content is **not** released. A normal turn is unaffected.
**Faithful or net-new:** **Net-new mechanism, design-aligned** — listed as M6 hardening, but it touches the envelope, so **I need your go-ahead before building.** **Effort: L.**

---

### M11 — The Planner Awakens (Nexus-Mind depth) + Your Own Documents — *owner-gated*
**Goal:** Give the orchestrator a genuine (if minimal) planning seam, and let Aletheia work on *your* material.
**Builds on:** M7 + M8 (trust and stop button in place before ingesting arbitrary documents) + M10 (grounding scores make new-corpus answers honestly measurable).
**What gets built:**
- A real decomposition step in the Nexus-Mind (LLM-backed, behind the provider): classify the request, choose a pathway, emit a typed task definition — even if it still resolves to one path today, the seam is real and two SCC verbs (`INITIATE_TASK`, `REPORT_FINDINGS_OUTPUT`) get used. *(This is a first taste of the SCC verb layer, not full adoption — see deferred gap below.)*
- An **input-sanitization / prompt-injection floor** before the LLM (the net-new safety item from §4–§5) — deterministic first, mirroring the Philosopher.
- `/ingest <path>` and `--corpus` to point Aletheia at your own folder; multi-format loaders (Markdown, text, PDF) behind the corpus interface.
- Citations drill-down in the UI (source + evidence sentence + confidence per claim).

**Done-when demo:** Point Aletheia at a folder of your own PDFs, ask a relational question, watch the Nexus-Mind classify-and-route in the log, get a grounded answer (with M10's faithfulness score), and click any claim to see the exact source sentence.
**Faithful or net-new:** Mostly faithful (restores the Nexus-Mind's designed role; surfaces existing provenance). The corpus default-flip, PDF support, and input-sanitization floor are net-new — **owner decisions 2, 4, and 6 below.** **Effort: L.**

---

### M12a — Durable Learning (close the RFC-001 gaps) — *faithful*
**Goal:** Make self-improvement durable and complete the learning design.
**Builds on:** M5 (the in-process Resonance Cycle) + M7 (durable audit).
**What gets built:**
- Durable, on-disk snapshots + audit history so rollback survives restarts (closes the M5 caveat — the correctness gap behind its PARTIAL verdict).
- The memory-correction **L1 learning** path (the missing half of L1/L2), with provenance and reversibility.
- Broader policy levers and a real Diagnostician-driven **post-deploy monitoring loop** (RFC-001's live dissonance watch). *(Brushes the "Human Gavel forever" default — monitoring only* observes *and recommends; it never auto-applies. Confirm in decision 3.)*

**Done-when demo:** Apply a self-improvement, restart the process, roll it back successfully (impossible today). Give corrective feedback and watch a fact get annotated in memory (L1), not just a policy flipped (L2).
**Faithful or net-new:** Faithful — completes RFC-001. **Effort: L.**

---

### M12b — Optional Scale-Up — *owner-gated, separable*
**Goal:** Prove the enterprise path runs with zero agent-code changes — only as far as you want it.
**Builds on:** M12a (interfaces promoted) + the existing `MessageBus`/`VectorStore`/`GraphStore` seams.
**What gets built (behind one config switch + a `docker-compose`):**
- Redis/NATS bus + Postgres policy/log store + Chroma embeddings + model routing (Haiku/Opus) + prompt caching — proven to run with identical behaviour.

**Done-when demo:** Flip one env switch and run the *same* cascade on Redis+Postgres+Chroma with identical behaviour and an unchanged Glass Box.
**Faithful or net-new:** Faithful-but-owner-gated (introduces services you'd run — bundled in Docker, still local, no cloud). **Effort: XL — scope with you before starting.**

---

### Named gaps deferred beyond v2 (explicit, not dropped)

These are real design elements with no v2 milestone home, listed so they don't silently vanish — each needs a future owner decision:
- **Full SCC verb vocabulary + the SDF extensibility process.** M11 uses two verbs as a seam; wholesale adoption (and the propose→review→version→rollout SDF workflow) is a v3 effort.
- **The consensus mechanism** (multi-agent sign-off before a policy change — the `REQUEST_CONSENSUS` family). Faithful, but L-effort with no dependency yet; deferred to v3.
- **InterestProfile re-tuning** (built-but-dormant). Deferred to v3.
- **Prime Directives 2 & 3 full detection.** v2 ships only conservative rule-floor predicates; genuine detection of "flawed motivation" is an open research problem (CLAUDE.md §7) and is honestly out of v2 scope.
- **Per-agent process/network isolation (Defense-in-depth Layer 5).** Only meaningful once M12b makes agents separate processes; v3.
- **OpenTelemetry export, conversation memory.** Net-new; deferred pending the owner decisions below.

---

### Decisions I need from you

1. **Message signing (M9).** The right fix for agents-trusting-each-other, but it adds a `Signature` field to the envelope plus key management. Approve as faithful hardening, or defer? *(I recommend approve — it's the one critical gap that's a true safety bypass.)*
2. **Your own documents (M11).** Your standing default is "Q&A over Aletheia's own docs." Keep self-docs as the default and add yours as opt-in, or switch the default to your material?
3. **How far up the infra ladder (M12b), and the monitoring loop (M12a).** Durable rollback and L1 learning (M12a) are pure wins. The post-deploy monitoring loop only *observes and recommends* (never auto-applies — Human Gavel stays). The Redis/Postgres/Chroma scale-up (M12b) introduces services *you'd* run (bundled in Docker, still local). Build M12b now, or keep it as a proven-but-unused capability until you need multi-process?
4. **PDF/format breadth (M11).** Cap at Markdown+text+PDF, or include HTML/web pages too? (More formats = messier grounding, surfaced honestly via confidence scores.)
5. **Eval strictness (M10).** Confirm the staged approach: start grounding-veto in *flag-and-escalate* mode and only harden to hard-reject once the acceptance bar (FP ≤ 5% over ≥100 graded answers across two CI runs) is met — meaning some ungrounded answers ship *flagged* at first rather than blocked.
6. **Input-sanitization floor (M11) — net-new.** A deterministic prompt-injection/sanitization gate before the LLM, serving Directive 1. It's an addition the design doesn't spell out, so under the prime rule it needs your nod. *(I recommend approve — it directly addresses the project's own canonical failure.)*
7. **Log redaction (M7) — design-touching.** Redacting secrets/PII before they hit the Cascade Log trades a sliver of Glass-Box completeness for privacy. Approve redaction, or keep the log fully complete and protect it by access control instead?
8. **Two net-new extras to keep or drop:** *OpenTelemetry export* (optional, off-by-default) and *conversation memory* (needs a careful design talk so chat history never becomes citable "fact"). In or out of v2?

**Recommended start:** build **M7 → M8 → M10** immediately (trust, safety, honest grounding — all faithful, no architecture call needed from you), and in parallel bring me your answers to decisions 1, 2, 6, and 7 so M9 and M11 can follow without stalling.
