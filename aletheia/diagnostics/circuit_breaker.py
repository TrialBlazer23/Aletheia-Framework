"""The Circuit Breaker — the systemic stop the Diagnostician trips on runaways.

CLAUDE.md §9 (defense-in-depth, Layer 3) gives the Diagnostician the job of
"trip[ping] circuit breakers" on loops/failures. This is that enforcement point.

It is deliberately dumb and lives at the *infrastructure* layer: the Diagnostician
decides **when** to trip and **who** to stop; the bus asks the breaker, before
every delivery, whether a message may flow. That keeps the agents untouched (they
never see the breaker) and the policy (detection) cleanly separated from the
mechanism (gating) — the same separation the rest of Aletheia is built on.

Two scopes:

* **Targeted** — block specific source UIDs (the agents caught in a loop). The
  rest of the Family keeps working, so the system *stays alive* while the runaway
  is contained — exactly what Milestone 3 requires.
* **Global** — a hard kill-switch that gates the whole bus (the emergency stop).

Tripping is recorded so every intervention is auditable, and ``reset`` /
``clear`` let a recovery cascade restore flow once the danger has passed.
"""

from __future__ import annotations

from dataclasses import dataclass

from aletheia.protocol.messages import SynapseMessage


@dataclass(frozen=True)
class BreakerTrip:
    """An audit record of one circuit-breaker intervention."""

    reason: str
    scope: str  # "GLOBAL" or "SOURCES"
    sources: tuple[str, ...] = ()
    correlation_id: str | None = None


class CircuitBreaker:
    """A gate the bus consults before delivering each message.

    Healthy by default (``blocks`` returns ``False`` for everything). The
    Diagnostician trips it to halt a runaway; a recovery cascade resets it.
    """

    def __init__(self) -> None:
        self._blocked_sources: set[str] = set()
        self._global: bool = False
        self.trips: list[BreakerTrip] = []  # append-only audit of interventions

    # --- state ------------------------------------------------------------- #
    @property
    def is_tripped(self) -> bool:
        return self._global or bool(self._blocked_sources)

    @property
    def blocked_sources(self) -> frozenset[str]:
        return frozenset(self._blocked_sources)

    @property
    def is_global(self) -> bool:
        return self._global

    def blocks(self, message: SynapseMessage) -> bool:
        """Whether this message must be gated (not delivered)."""
        if self._global:
            return True
        return message.source in self._blocked_sources

    # --- tripping (the Diagnostician's action) ----------------------------- #
    def trip_sources(
        self, sources: list[str] | set[str], *, reason: str, correlation_id: str | None = None
    ) -> BreakerTrip:
        """Contain a runaway: stop the named agents from propagating further."""
        self._blocked_sources.update(sources)
        trip = BreakerTrip(
            reason=reason,
            scope="SOURCES",
            sources=tuple(sorted(sources)),
            correlation_id=correlation_id,
        )
        self.trips.append(trip)
        return trip

    def trip_global(self, *, reason: str) -> BreakerTrip:
        """Emergency stop: gate the entire bus."""
        self._global = True
        trip = BreakerTrip(reason=reason, scope="GLOBAL")
        self.trips.append(trip)
        return trip

    # --- recovery ---------------------------------------------------------- #
    def reset_sources(self, sources: list[str] | set[str]) -> None:
        """Release specific agents (a targeted recovery)."""
        self._blocked_sources.difference_update(sources)

    def reset(self) -> None:
        """Full recovery: clear every block (the audit of trips is preserved)."""
        self._blocked_sources.clear()
        self._global = False
