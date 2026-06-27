"""Observability & self-healing internals for the Diagnostician (Milestone 3).

The Diagnostician agent lives in ``aletheia.agents.diagnostician``; this package
holds the infrastructure it drives — chiefly the :class:`CircuitBreaker`, the
systemic kill-switch the bus consults to stop a runaway cascade. Keeping the
breaker here (depending only on the protocol) lets the bus enforce it without
importing the agent, so there is no import cycle and the agents stay unchanged.
"""

from aletheia.diagnostics.circuit_breaker import CircuitBreaker, BreakerTrip

__all__ = ["CircuitBreaker", "BreakerTrip"]
