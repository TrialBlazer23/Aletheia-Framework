"""The Synapse Interface Layer / SIL (NSAP-0002).

Every Family member wraps its core logic in a SIL with two halves — a
``Listener`` ("the Ears" / Decoder) and a ``Broadcaster`` ("the Mouth" /
Encoder) — plus a declarative ``InterestProfile``. This is what makes the
Domino Cascade self-driving: agents react to each other without the Nexus-Mind
micromanaging.
"""

from aletheia.sil.broadcaster import Broadcaster
from aletheia.sil.interest_profile import InterestProfile, InterestRule
from aletheia.sil.listener import Listener, RelevantMessage

__all__ = [
    "InterestProfile",
    "InterestRule",
    "Listener",
    "RelevantMessage",
    "Broadcaster",
]
