"""The Family — Aletheia's specialized agents.

Milestone 0 shipped the ``FamilyMember`` base (SIL wiring + handshake).
Milestone 1 adds the first three living agents — Nexus-Mind, Archivist, Narrator.
The Philosopher, Diagnostician, and Visionary arrive in later milestones per
ROADMAP.md.
"""

from aletheia.agents.archivist import Archivist
from aletheia.agents.family import (
    ARCHIVIST_UID,
    DIAGNOSTICIAN_UID,
    NARRATOR_UID,
    NEXUS_MIND_UID,
    PHILOSOPHER_UID,
    VISIONARY_UID,
)
from aletheia.agents.family_member import FamilyMember
from aletheia.agents.narrator import Narrator
from aletheia.agents.nexus_mind import NexusMind, QAResult
from aletheia.agents.philosopher import Philosopher

__all__ = [
    "FamilyMember",
    "NexusMind",
    "QAResult",
    "Archivist",
    "Narrator",
    "Philosopher",
    "NEXUS_MIND_UID",
    "ARCHIVIST_UID",
    "NARRATOR_UID",
    "PHILOSOPHER_UID",
    "VISIONARY_UID",
    "DIAGNOSTICIAN_UID",
]
