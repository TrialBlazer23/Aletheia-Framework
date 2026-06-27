"""The versioned operational policy — the behaviour agents read at runtime.

CLAUDE.md §8 / RFC-001 §3: "Operational behavior lives in a versioned
``operational_policy.json``." This is that file plus the store that guards it.

The store is the home of two non-negotiable safety rails:

* **Snapshot before every change** — so any update is reversible.
* **Rollback** — restore the previous behaviour on command (or automatically, if
  a deployed change makes dissonance *worse*).

The policy itself is deliberately small in this milestone: the lever the
canonical RFC-001 scenario needs is ``distrusted_sources`` — sources the
Archivist must not treat as factual ground truth. New levers slot in here as
later behaviour becomes tunable; the store, versioning, and rollback don't change.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OperationalPolicy(BaseModel):
    """The runtime-tunable behaviour of the Family, as one versioned document."""

    model_config = ConfigDict(populate_by_name=True)

    version: int = Field(default=1, alias="Version")
    # Sources the Archivist must NOT treat as factual ground truth (the lever the
    # canonical satire scenario adjusts). Matched as case-insensitive substrings
    # of a passage/fact's source label.
    distrusted_sources: list[str] = Field(default_factory=list, alias="Distrusted_Sources")
    # The lowest retrieval confidence the Archivist will still ground an answer on.
    min_ingest_confidence: float = Field(default=0.0, alias="Min_Ingest_Confidence")
    notes: str = Field(default="", alias="Notes")

    def distrusts(self, source: str) -> bool:
        s = (source or "").lower()
        # Skip empty entries: an empty string is a substring of everything and
        # would silence all retrieval — a corrupt policy must not blind the system.
        return any(bad.lower() in s for bad in self.distrusted_sources if bad.strip())


class PolicyStore:
    """Holds the current policy and its snapshot history; persists to JSON.

    The snapshot stack is a simple LIFO, which assumes Resonance cycles run **one
    at a time** (the design: the Nexus-Mind drives a single supervised cycle, and
    the cycle is rate-limited). Concurrent cycles sharing one store would need a
    lock + per-change snapshot ids; that arrives with the multi-process upgrade.

    Parameters
    ----------
    path:
        Where to read/write ``operational_policy.json``. ``None`` keeps it purely
        in memory (tests/demos). If the file exists it is loaded; otherwise the
        default policy is written.
    policy:
        An explicit starting policy (overrides any file on disk).
    """

    def __init__(
        self, path: str | Path | None = "operational_policy.json", *, policy: OperationalPolicy | None = None
    ) -> None:
        self._path = Path(path) if path is not None else None
        self._snapshots: list[OperationalPolicy] = []  # past states, oldest → newest
        self._audit: list[dict] = []  # append-only log of apply/rollback events

        if policy is not None:
            self._current = policy.model_copy(deep=True)
        elif self._path is not None and self._path.is_file():
            self._current = OperationalPolicy.model_validate_json(self._path.read_text("utf-8"))
        else:
            self._current = OperationalPolicy()
        self._persist()

    # --- access ------------------------------------------------------------ #
    @property
    def current(self) -> OperationalPolicy:
        return self._current

    @property
    def version(self) -> int:
        return self._current.version

    @property
    def history(self) -> list[dict]:
        return list(self._audit)

    @property
    def snapshot_count(self) -> int:
        return len(self._snapshots)

    # --- mutation (always snapshots first) --------------------------------- #
    def apply(self, new_policy: OperationalPolicy, *, reason: str = "") -> OperationalPolicy:
        """Snapshot the current policy, then make ``new_policy`` current (v+1)."""
        self._snapshots.append(self._current.model_copy(deep=True))
        bumped = new_policy.model_copy(deep=True)
        bumped.version = self._current.version + 1
        prior = self._current.version
        self._current = bumped
        self._persist()
        self._audit.append(
            {
                "event": "APPLY",
                "from_version": prior,
                "to_version": bumped.version,
                "reason": reason,
                "at": _utc_now_iso(),
            }
        )
        return self._current

    def rollback(self, *, reason: str = "") -> OperationalPolicy:
        """Restore the most recent snapshot (undo the last apply)."""
        if not self._snapshots:
            return self._current
        restored = self._snapshots.pop()
        prior = self._current.version
        self._current = restored
        self._persist()
        self._audit.append(
            {
                "event": "ROLLBACK",
                "from_version": prior,
                "to_version": restored.version,
                "reason": reason,
                "at": _utc_now_iso(),
            }
        )
        return self._current

    # --- persistence ------------------------------------------------------- #
    def _persist(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._current.model_dump(by_alias=True), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
