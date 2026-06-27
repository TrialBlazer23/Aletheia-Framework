# The Aletheia Framework

### (Formerly Project Chimera)

**A Neuro-Symbolic Standard for Auditable, Self-Healing Agent Ecosystems.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Active Development](https://img.shields.io/badge/Status-Active%20Development-green.svg)]()
[![Architecture: Neuro-Symbolic](https://img.shields.io/badge/Architecture-Neuro--Symbolic-blueviolet.svg)]()
[![Implementation: M0–M6](https://img.shields.io/badge/Implementation-M0–M6%20(Family%20complete)-success.svg)]()

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/TrialBlazer23/Aletheia-Framework)

> **Current Status (June 2026):** **Milestones 0–6 are built, tested, and runnable — the six-agent Family is complete.** The Synapse nervous system, the Domino Cascade, the full Family (Nexus-Mind, Archivist, Narrator, Philosopher, Diagnostician, Visionary), the knowledge-graph memory, the supervised **Resonance Cycle** with the **Human Gavel**, and the creative cascade. The whole system runs with one command (`python main.py`) and is covered by a passing test suite. See [`ROADMAP.md`](docs/ROADMAP.md) for the build plan and [`CLAUDE.md`](CLAUDE.md) for the canonical design.

> **The Philosophy:** Current AI models are Black Boxes. Aletheia is a **Glass Box**. It separates *Generation* (The Narrator) from *Judgment* (The Philosopher) to create agents that are safe, auditable, and capable of recursive self-improvement.
> *Read the origin story and architectural thesis in [VISION.md](docs/VISION.md).*

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

### Run it in the cloud — GitHub Codespaces (easiest, nothing to install)

A **Codespace** is a full computer that runs in your browser — no local setup, no terminal on your own machine. This repo ships a dev-container, so the Codespace installs everything for you automatically.

1. **Open a Codespace.** On the repo's GitHub page, click the green **`< > Code`** button → the **Codespaces** tab → **Create codespace on main**. (Or just click the **Open in GitHub Codespaces** badge at the top of this README.)
2. **Wait ~2–3 minutes** the first time while it builds. When the terminal shows **`✅ Aletheia is ready`**, it's done.
3. **Run it** by typing this in the terminal at the bottom and pressing Enter:
   ```bash
   python main.py
   ```
   Then type a question like *"What does the Philosopher enforce?"* and press Enter. Try `/create a bioluminescent deep-sea creature` for the creative cascade, or `/quit` to exit.

   **Prefer a web page?** Run `python main.py --web` instead. Codespaces will pop up a notification to **Open in Browser** — that's a clean point-and-click interface where you can ask questions, request creature designs (with color-palette swatches), and watch the Domino Cascade hop between the agents. No terminal needed once it's open.

**Turn on live Claude (optional).** Without a key, Aletheia runs in a free **offline mode** (it still works — it returns grounded extracts instead of Claude-composed prose). To get full Claude answers, add your Anthropic API key as a **Codespaces secret** so it's stored securely and never committed:
* Go to **https://github.com/settings/codespaces** → **Secrets** → **New secret**.
* **Name:** `ANTHROPIC_API_KEY`  **Value:** your key (`sk-ant-...`)  **Repository access:** select **Aletheia-Framework**.
* Back in the Codespace, click the menu (≡) → **Reload Window** (or stop & restart the Codespace) so it picks up the secret. Run `python main.py` again — it should say *"Narrator brain: Anthropic Claude"*.

> 💡 Codespaces gives every personal GitHub account a generous free monthly allowance. **Stop your Codespace when you're done** (github.com/codespaces → **⋯** → Stop) so it doesn't keep using hours.

### See it work — the milestone demos
Each runs end-to-end and prints what's happening:
```bash
python main.py --web          # a browser interface (needs: pip install -e ".[web]")
python main.py --creative     # the full Family makes a safety-checked creative asset
python main.py --resonance    # the system heals itself from a bad fact (Human Gavel)
python main.py --knowledge    # answers a relational question by graph traversal
python main.py --diagnostics  # induces a loop + a hung agent; the Diagnostician contains them
python main.py --handshake    # the very first two-agent handshake over the bus
python -m pytest              # the full test suite
```

### Run it on your own machine instead (optional)
Prerequisite: **Python 3.11+**.
```bash
git clone https://github.com/TrialBlazer23/Aletheia-Framework.git
cd Aletheia-Framework
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev,graph]"     # the [graph] extra adds spaCy + the knowledge graph
python main.py
```
To enable live Claude locally, copy `.env.example` to `.env` and paste your key (the `.env` file is git-ignored):
```bash
cp .env.example .env              # then edit .env and add ANTHROPIC_API_KEY=sk-ant-...
```

---

## 📊 Documentation

* **[`CLAUDE.md`](CLAUDE.md)** — the canonical design + build conventions (single source of truth for *what the system must be*).
* **[`ROADMAP.md`](docs/ROADMAP.md)** — the real, milestone-by-milestone build plan we follow.
* **[VISION.md](docs/VISION.md)** — the manifesto and architectural thesis.
* **[QUICK_ASSESSMENT.md](docs/QUICK_ASSESSMENT.md)** / **[ANALYSIS.md](docs/ANALYSIS.md)** — feasibility analysis and technical review.
* **[IMPLEMENTATION_ROADMAP.md](docs/IMPLEMENTATION_ROADMAP.md)** — the aspirational enterprise-scale timeline (for reference; `ROADMAP.md` is what we actually follow).

---

## 📂 Repository Structure

* `/aletheia`: the implementation — `protocol/` (Synapse), `bus/` (Domino Cascade), `sil/` (Interface Layer), `agents/` (the Family), `safety/` (Prime Directives + validator), `memory/`, `sdr/`, `llm/`, `app/`, `log/`.
* `/tests`: the test suite.
* `/Architecture`, `/Standards`, `/Safety_Protocols`, `/RFCs`: the design specifications (the source of truth the implementation is built from).
* `/docs`: analysis & planning — `VISION.md`, `ROADMAP.md`, `IMPLEMENTATION_ROADMAP.md`, `ANALYSIS.md`, `QUICK_ASSESSMENT.md`, `GLOSSARY.md`. (`CLAUDE.md`, the canonical design, stays at the repo root.)

---

## 🤝 Contributing

We are looking for architects, ethicists, and engineers to help build the **Glass Box** future.

* **Engineers:** Help refine the *Domino Cascade* event bus and the Family of agents.
* **Philosophers:** Help expand the ethical rule sets for the *Philosopher* agent.

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
