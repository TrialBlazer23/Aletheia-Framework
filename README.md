# The Aletheia Framework

### (Formerly Project Chimera)

**A Neuro-Symbolic Standard for Auditable, Self-Healing Agent Ecosystems.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Active Development](https://img.shields.io/badge/Status-Active%20Development-green.svg)]()
[![Architecture: Neuro-Symbolic](https://img.shields.io/badge/Architecture-Neuro--Symbolic-blueviolet.svg)]()
[![Implementation: Alpha](https://img.shields.io/badge/Implementation-Alpha%20(M0–M2)-orange.svg)]()

> **Current Status (June 2026):** Implementation is underway. **Milestones 0–2 are built and runnable** — the Synapse nervous system, the first living 3-agent cascade (Nexus-Mind → Archivist → Narrator), and the Philosopher safety kernel enforcing the Prime Directives. The whole system runs locally with one command (`python main.py`) and is covered by a passing test suite. See [`ROADMAP.md`](ROADMAP.md) for the build plan and [`CLAUDE.md`](CLAUDE.md) for the canonical design.

> **The Philosophy:** Current AI models are Black Boxes. Aletheia is a **Glass Box**. It separates *Generation* (The Narrator) from *Judgment* (The Philosopher) to create agents that are safe, auditable, and capable of recursive self-improvement.
> *Read the origin story and architectural thesis in [VISION.md](VISION.md).*

---

## 🏗️ The Architecture

Aletheia is not a single model. It is a **Multi-Agent System (MAS)** composed of specialized "Organs" that communicate via the **Domino Cascade** (event bus).

### 1. The Family (Agent Roles)

| Agent | Role | Function | Status |
| --- | --- | --- | --- |
| **Nexus-Mind** | Orchestrator | Strategic planning, task decomposition, and resource allocation. The "System 2" thinker. | ✅ Built (M1) |
| **Archivist** | Memory Core | Manages grounded memory; retrieves context with source attribution. Knowledge graph via deterministic parsing arrives in M4. | ✅ Built (M1) |
| **Narrator** | Interface | Synthesizes complex data into a human-readable answer. Generation only. | ✅ Built (M1) |
| **Philosopher** | Ethical Kernel | A neuro-symbolic auditor that validates outputs against the "Prime Directives" *before* release, with veto power. | ✅ Built (M2) |
| **Diagnostician** | Self-Healing | Monitors the event bus for loops/failures, trips circuit breakers, emits health telemetry. | ⏳ Planned (M3) |
| **Visionary** | Simulation | Predictive modeling and creative asset generation. | ⏳ Planned (M6) |

### 2. Core Mechanics

#### The Domino Cascade (Event-Driven Flow)

Agents don't wait for orders — they listen for events and react, producing a chain reaction. Every hop is recorded in the append-only **Cascade Log** (the Glass Box audit trail).

> *Live example (built):* `USER_INPUT` → **Nexus-Mind** `TRIGGER` → **Archivist** `DATA_VALIDATED` → **Narrator** `DRAFT_READY` → **Philosopher** `APPROVED` → **User**.

#### The Resonance Cycle (Recursive Improvement) — *planned (M5)*

The system learns from its own logged failures: it traces the Cascade Log to a root cause, proposes a policy update, has the Philosopher verify it in a sandbox, and applies it only after human approval (the "Human Gavel").

---

## 🚀 Getting Started

The whole system runs locally — no cloud services required.

### Prerequisites
* Python 3.11+

### Installation
```bash
git clone https://github.com/TrialBlazer23/Aletheia-Framework.git
cd Aletheia-Framework
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

### Running it
```bash
python main.py              # Q&A console — ask Aletheia about its own design
python main.py --handshake  # the Milestone 0 two-agent handshake demo
python -m pytest            # the test suite
```

**Live Claude vs. offline mode:** by default the Narrator uses Anthropic Claude. Provide a key and you get Claude-composed answers; without one, the system runs in a free **offline mode** that returns grounded extracts from the documents (it never fails — it degrades gracefully). To enable live Claude, copy `.env.example` to `.env` and paste your key (the `.env` file is git-ignored):
```bash
cp .env.example .env        # then edit .env and add ANTHROPIC_API_KEY=sk-ant-...
```

---

## 📊 Documentation

* **[`CLAUDE.md`](CLAUDE.md)** — the canonical design + build conventions (single source of truth for *what the system must be*).
* **[`ROADMAP.md`](ROADMAP.md)** — the real, milestone-by-milestone build plan we follow.
* **[VISION.md](VISION.md)** — the manifesto and architectural thesis.
* **[QUICK_ASSESSMENT.md](QUICK_ASSESSMENT.md)** / **[ANALYSIS.md](ANALYSIS.md)** — feasibility analysis and technical review.
* **[IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md)** — the aspirational enterprise-scale timeline (for reference; `ROADMAP.md` is what we actually follow).

---

## 📂 Repository Structure

* `/aletheia`: the implementation — `protocol/` (Synapse), `bus/` (Domino Cascade), `sil/` (Interface Layer), `agents/` (the Family), `safety/` (Prime Directives + validator), `memory/`, `sdr/`, `llm/`, `app/`, `log/`.
* `/tests`: the test suite.
* `/Architecture`, `/Standards`, `/Safety_Protocols`, `/RFCs`: the design specifications (the source of truth the implementation is built from).
* Analysis & planning: `CLAUDE.md`, `ROADMAP.md`, `ANALYSIS.md`, `QUICK_ASSESSMENT.md`.

---

## 🤝 Contributing

We are looking for architects, ethicists, and engineers to help build the **Glass Box** future.

* **Engineers:** Help refine the *Domino Cascade* event bus and the Family of agents.
* **Philosophers:** Help expand the ethical rule sets for the *Philosopher* agent.

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
