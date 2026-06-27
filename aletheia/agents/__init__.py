"""The Family — Aletheia's specialized agents.

Milestone 0 ships only the ``FamilyMember`` base class (the SIL wiring + the
handshake). The six concrete agents — Nexus-Mind, Archivist, Narrator,
Philosopher, Visionary, Diagnostician — arrive in later milestones per
ROADMAP.md.
"""

from aletheia.agents.family_member import FamilyMember

__all__ = ["FamilyMember"]
