"""The Listener ("the Ears" / Decoder) — NSAP-0002.

Required functions per the spec:

* ``scanNetwork()`` — monitor the broadcast stream (here: receive each message
  the bus delivers).
* ``filterRelevantMessages(message)`` — keep only messages this agent cares
  about, matched against its Interest Profile (plus any TRIGGER addressed
  directly to this agent's UID).
* ``parsePayload(payload)`` — extract the actionable data from a relevant
  message.
* ``triggerParentModel(data)`` — hand the decoded action + data to the parent
  agent's core logic.

This class implements ``filter`` and ``parse``; ``triggerParentModel`` is the
agent's job (the ``FamilyMember`` base wires it up).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aletheia.protocol.messages import MessageType, SynapseMessage
from aletheia.sil.interest_profile import InterestProfile


@dataclass(frozen=True)
class RelevantMessage:
    """A message the agent should act on, decoded into an action + data."""

    action: str
    data: dict[str, Any]
    message: SynapseMessage


class Listener:
    def __init__(self, owner_uid: str, interest_profile: InterestProfile) -> None:
        self._owner_uid = owner_uid
        self._profile = interest_profile

    @property
    def interest_profile(self) -> InterestProfile:
        return self._profile

    def filter_relevant_messages(self, message: SynapseMessage) -> RelevantMessage | None:
        """Return a decoded action if this message concerns the parent, else None."""
        # An agent never reacts to its own broadcast (prevents trivial loops).
        if message.source == self._owner_uid:
            return None

        # 1) A TRIGGER addressed directly to this agent is always relevant; its
        #    action and parameters come straight off the body.
        if message.type == MessageType.TRIGGER:
            body = message.body  # TriggerBody
            if body.target_uid == self._owner_uid:  # type: ignore[union-attr]
                return RelevantMessage(
                    action=body.action_to_trigger,  # type: ignore[union-attr]
                    data=self._parse_payload(message),
                    message=message,
                )
            return None

        # 2) EVENT / STATE_CHANGE: relevance is decided by the Interest Profile.
        rule = self._profile.first_match(message)
        if rule is None:
            return None
        return RelevantMessage(
            action=rule.action_to_trigger,
            data=self._parse_payload(message),
            message=message,
        )

    def _parse_payload(self, message: SynapseMessage) -> dict[str, Any]:
        """Translate a Synapse body into a plain dict for the parent model."""
        body = message.body
        if message.type == MessageType.TRIGGER:
            return {
                "parameters": dict(body.parameters),  # type: ignore[union-attr]
                "on_event": body.condition.on_event,  # type: ignore[union-attr]
            }
        if message.type == MessageType.EVENT:
            payload = body.payload  # type: ignore[union-attr]
            return {
                "event_name": body.event_name,  # type: ignore[union-attr]
                "data_asset_uid": payload.data_asset_uid,
                "description": payload.description,
                "confidence_score": payload.confidence_score,
            }
        # STATE_CHANGE
        return {
            "status_code": body.status_code,  # type: ignore[union-attr]
            "reason": body.reason,  # type: ignore[union-attr]
            "target_uid": body.target_uid,  # type: ignore[union-attr]
        }
