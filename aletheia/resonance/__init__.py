"""The Resonance Cycle (Milestone 5) — supervised self-improvement.

RFC-001 / NSAP-ARCH-003: the system turns its own logged failures into wisdom,
with a human holding the gavel. Four phases — **Dissonance Detection → Harmonic
Analysis → Proposal Generation → Integration** — wrapped in non-negotiable
safety rails: every proposal is simulated in an isolated **Resonance Sandbox**,
verified by the Philosopher against the Prime Directives, rate-limited,
snapshotted for **rollback**, and applied only after the **Human Gavel**.

Public surface:

* ``OperationalPolicy`` / ``PolicyStore`` — the versioned, rollback-able config
  agents read at runtime.
* ``PerformanceAnalyzer`` — the four "System Harmony" indices + dissonance.
* ``ResonanceSandbox`` — isolated simulation of a proposed change.
* ``HumanGavel`` (+ implementations) — the human-in-the-loop gate.
* ``ResonanceEngine`` — orchestrates the four phases end to end.
"""

from aletheia.resonance.analytics import (
    DissonanceEvent,
    Feedback,
    PerformanceAnalyzer,
)
from aletheia.resonance.engine import (
    CallbackGavel,
    ConsoleGavel,
    GavelDecision,
    HumanGavel,
    RateLimiter,
    ResonanceEngine,
    ResonanceOutcome,
)
from aletheia.resonance.policy import OperationalPolicy, PolicyStore
from aletheia.resonance.sandbox import ResonanceSandbox, SandboxResult

__all__ = [
    "OperationalPolicy",
    "PolicyStore",
    "PerformanceAnalyzer",
    "Feedback",
    "DissonanceEvent",
    "ResonanceSandbox",
    "SandboxResult",
    "HumanGavel",
    "CallbackGavel",
    "ConsoleGavel",
    "GavelDecision",
    "RateLimiter",
    "ResonanceEngine",
    "ResonanceOutcome",
]
