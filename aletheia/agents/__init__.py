"""The Family — Aletheia's specialized agents.

Milestone 0 shipped the ``FamilyMember`` base (SIL wiring + handshake).
Milestone 1 adds the first three living agents — Nexus-Mind, Archivist, Narrator.
Milestone 2 adds the Philosopher; Milestone 3 the Diagnostician; Milestone 6 the
Visionary — completing the six-agent Family.
"""

from aletheia.agents.archivist import Archivist
from aletheia.agents.diagnostician import Diagnostician
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
from aletheia.agents.nexus_mind import CreativeResult, NexusMind, QAResult
from aletheia.agents.philosopher import Philosopher
from aletheia.agents.visionary import Visionary

__all__ = [
    "FamilyMember",
    "NexusMind",
    "QAResult",
    "CreativeResult",
    "Archivist",
    "Narrator",
    "Philosopher",
    "Diagnostician",
    "Visionary",
    "NEXUS_MIND_UID",
    "ARCHIVIST_UID",
    "NARRATOR_UID",
    "PHILOSOPHER_UID",
    "VISIONARY_UID",
    "DIAGNOSTICIAN_UID",
]
