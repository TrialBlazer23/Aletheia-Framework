"""The Cascade Log — the append-only Glass Box record of the Domino Cascade.

CLAUDE.md §10: *"The Cascade Log is sacred. Every message in, every message out,
append-only. Build it first, never bypass it."* This is that record.

Every Synapse message that crosses the bus is appended here as one JSON line
(JSONL), wrapped with a monotonic sequence number and a capture timestamp. The
result is a complete, replayable, human-readable audit trail — the foundation
the Diagnostician and the Resonance Cycle will later build on.

The log can also write to an in-memory buffer (no file) for tests and demos.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aletheia.protocol.messages import SynapseMessage


class CascadeLog:
    """Append-only sink for every message on the bus.

    Parameters
    ----------
    path:
        Where to append JSONL records. If ``None``, records are kept only in an
        in-memory buffer (useful for tests). Parent directories are created.
    """

    def __init__(self, path: str | Path | None = "cascade_log.jsonl") -> None:
        self._path = Path(path) if path is not None else None
        self._lock = threading.Lock()  # appends must be atomic across tasks
        self._seq = 0
        self._buffer: list[dict[str, Any]] = []
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, message: SynapseMessage) -> dict[str, Any]:
        """Append one message to the log. Returns the written record."""
        with self._lock:
            self._seq += 1
            record = {
                "seq": self._seq,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "message": message.to_wire(),
            }
            self._buffer.append(record)
            if self._path is not None:
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            return record

    @property
    def entries(self) -> list[dict[str, Any]]:
        """All records captured so far (in order)."""
        with self._lock:
            return list(self._buffer)

    def pretty(self) -> str:
        """A compact, human-readable rendering of the cascade so far."""
        lines = []
        for rec in self.entries:
            msg = rec["message"]
            header = msg["Header"]
            mtype = header["Message-Type"]
            source = header["Source-UID"]
            body = msg["Body"]
            if mtype == "EVENT":
                detail = f"{body['Event-Name']} -> {body['Payload']['Data-Asset-UID']}"
            elif mtype == "TRIGGER":
                detail = (
                    f"{body['Action-To-Trigger']} -> {body['Target-UID']}"
                    f" (on {body['Condition']['On-Event']})"
                )
            else:  # STATE_CHANGE
                detail = f"{body['Status-Code']} re {body['Target-UID']}: {body['Reason']}"
            lines.append(f"[{rec['seq']:>3}] {mtype:<12} {source:<22} {detail}")
        return "\n".join(lines)
