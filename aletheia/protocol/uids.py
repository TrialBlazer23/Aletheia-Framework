"""UID helpers for the Synapse Protocol.

Per the design, every addressable thing in Aletheia has a UID of the form
``CATEGORY:TYPE:IDENTIFIER`` — for example ``MODEL:Archivist:0x00A1``,
``ASSET:KNOWLEDGE_GRAPH:0xK1L2``, ``MSG:0x4F5A``.

UIDs are the universal glue: messages reference sources/targets by UID, the
Interface Layer filters on source UIDs, and SDR data assets are addressed by
UID. We keep the format strict but the identifier flexible (the design uses
hex-like tokens such as ``0x00A1``).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class UID:
    """A parsed ``CATEGORY:TYPE:IDENTIFIER`` unique identifier.

    Stored structurally so code can reason about category/type, but it renders
    back to the exact ``CATEGORY:TYPE:IDENTIFIER`` string on the wire.
    """

    category: str
    type: str
    identifier: str

    def __str__(self) -> str:  # render to the canonical wire form
        return f"{self.category}:{self.type}:{self.identifier}"

    @classmethod
    def parse(cls, raw: str) -> "UID":
        parts = raw.split(":")
        if len(parts) != 3 or not all(parts):
            raise ValueError(
                f"Invalid UID {raw!r}: expected 'CATEGORY:TYPE:IDENTIFIER'"
            )
        category, type_, identifier = parts
        return cls(category=category, type=type_, identifier=identifier)


def _short_hex(nbytes: int = 2) -> str:
    """A short hex token like ``0x4F5A`` in the style of the design docs."""
    return "0x" + secrets.token_hex(nbytes).upper()


def new_uid(category: str, type_: str, identifier: str | None = None) -> str:
    """Build a UID string, minting a fresh identifier if one isn't given."""
    return str(UID(category, type_, identifier or _short_hex()))


def new_message_id() -> str:
    """Mint a new ``MSG:0x....`` message identifier."""
    return f"MSG:{_short_hex(3)}"
