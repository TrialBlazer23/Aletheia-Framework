"""``InterestProfile`` — an agent's declarative subscription list.

Per NSAP-0002, each Listener is configured with an Interest Profile: "when I see
*this source + type + event/status*, run *this action*." It is **mutable** — the
system can re-tune what each agent listens for as it learns (this is the hook the
Resonance Cycle will later use).

Profiles are plain JSON so they can live on disk next to each agent, e.g.::

    {
      "listensFor": [
        {
          "source_model_UID": "MODEL:Archivist:0x00A1",
          "message_type": "EVENT",
          "event_name": "DATA_VALIDATED",
          "action_to_trigger": "GENERATE_NARRATIVE_DRAFT"
        }
      ]
    }

A rule field left as ``None``/absent is a wildcard (matches anything).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from aletheia.protocol.messages import MessageType, SynapseMessage


@dataclass(frozen=True)
class InterestRule:
    """One subscription: a match pattern + the action it triggers."""

    action_to_trigger: str
    source_model_uid: str | None = None
    message_type: MessageType | None = None
    event_name: str | None = None  # for EVENT messages
    status_code: str | None = None  # for STATE_CHANGE messages

    def matches(self, message: SynapseMessage) -> bool:
        header = message.header
        if self.source_model_uid is not None and header.source_uid != self.source_model_uid:
            return False
        if self.message_type is not None and header.message_type != self.message_type:
            return False
        if self.event_name is not None:
            if header.message_type != MessageType.EVENT:
                return False
            if message.body.event_name != self.event_name:  # type: ignore[union-attr]
                return False
        if self.status_code is not None:
            if header.message_type != MessageType.STATE_CHANGE:
                return False
            if message.body.status_code != self.status_code:  # type: ignore[union-attr]
                return False
        return True


class InterestProfile:
    """A mutable, ordered collection of :class:`InterestRule`."""

    def __init__(self, rules: list[InterestRule] | None = None) -> None:
        self._rules: list[InterestRule] = list(rules or [])

    @property
    def rules(self) -> list[InterestRule]:
        return list(self._rules)

    def add(self, rule: InterestRule) -> None:
        self._rules.append(rule)

    def first_match(self, message: SynapseMessage) -> InterestRule | None:
        for rule in self._rules:
            if rule.matches(message):
                return rule
        return None

    # --- (de)serialization ------------------------------------------------- #
    @classmethod
    def from_dict(cls, data: dict) -> "InterestProfile":
        rules = []
        for raw in data.get("listensFor", []):
            mtype = raw.get("message_type")
            rules.append(
                InterestRule(
                    action_to_trigger=raw["action_to_trigger"],
                    source_model_uid=raw.get("source_model_UID"),
                    message_type=MessageType(mtype) if mtype else None,
                    event_name=raw.get("event_name"),
                    status_code=raw.get("status_code"),
                )
            )
        return cls(rules)

    @classmethod
    def load(cls, path: str | Path) -> "InterestProfile":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
