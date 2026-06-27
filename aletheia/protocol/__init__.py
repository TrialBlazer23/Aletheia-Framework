"""The Synapse Protocol (NSAP-0001) — the message contract.

Every message on the Domino Cascade is a ``SynapseMessage``: a universal Header
plus a Body whose shape depends on the Message-Type (EVENT, TRIGGER,
STATE_CHANGE). Field names on the wire are exact per the spec (e.g.
``Message-ID``, ``Source-UID``); see ``messages.py``.
"""

from aletheia.protocol.messages import (
    EventBody,
    EventPayload,
    MessageType,
    StateChangeBody,
    SynapseHeader,
    SynapseMessage,
    TriggerBody,
    TriggerCondition,
    make_event,
    make_state_change,
    make_trigger,
)
from aletheia.protocol.uids import UID, new_message_id, new_uid

__all__ = [
    "MessageType",
    "SynapseHeader",
    "SynapseMessage",
    "EventBody",
    "EventPayload",
    "TriggerBody",
    "TriggerCondition",
    "StateChangeBody",
    "make_event",
    "make_trigger",
    "make_state_change",
    "UID",
    "new_uid",
    "new_message_id",
]
