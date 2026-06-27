"""Synapse Protocol 2.0 message types (NSAP-0001).

Every message has a universal **Header** and a **Body** whose shape depends on
the ``Message-Type``. The wire field names are the contract and are preserved
exactly (``Message-ID``, ``Source-UID``, ``Timestamp``, ``Message-Type``,
``Protocol-Ver``; ``Event-Name``, ``Data-Asset-UID``, ``Confidence-Score``;
``Target-UID``, ``On-Event``, ``Action-To-Trigger``; ``Status-Code`` ...).

We model them with Pydantic and use field *aliases* so Python code can use
clean snake_case while serialization (``model_dump(by_alias=True)`` /
``model_dump_json(by_alias=True)``) emits the exact hyphenated spec names.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Union

from pydantic import BaseModel, ConfigDict, Field

from aletheia.protocol.uids import new_message_id

PROTOCOL_VERSION = "2.0"


class MessageType(str, Enum):
    """The three Synapse message types that drive the Domino Cascade."""

    EVENT = "EVENT"  # announces a completed action; the engine of the cascade
    TRIGGER = "TRIGGER"  # directly commands a model, optionally conditionally
    STATE_CHANGE = "STATE_CHANGE"  # reports operational status (handshake/health)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class _SynapseModel(BaseModel):
    """Base config: allow population by python name, serialize by spec alias."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


# --------------------------------------------------------------------------- #
# Header (present on every message)
# --------------------------------------------------------------------------- #
class SynapseHeader(_SynapseModel):
    message_id: str = Field(default_factory=new_message_id, alias="Message-ID")
    source_uid: str = Field(alias="Source-UID")
    timestamp: datetime = Field(default_factory=_utc_now, alias="Timestamp")
    message_type: MessageType = Field(alias="Message-Type")
    protocol_ver: str = Field(default=PROTOCOL_VERSION, alias="Protocol-Ver")


# --------------------------------------------------------------------------- #
# EVENT — announces a completed action and broadcasts a new data asset
# --------------------------------------------------------------------------- #
class EventPayload(_SynapseModel):
    data_asset_uid: str = Field(alias="Data-Asset-UID")
    description: str = Field(default="", alias="Description")
    # 0.0–1.0 certainty in the result. Optional because not every event carries one.
    confidence_score: float | None = Field(default=None, alias="Confidence-Score")


class EventBody(_SynapseModel):
    event_name: str = Field(alias="Event-Name")
    payload: EventPayload = Field(alias="Payload")


# --------------------------------------------------------------------------- #
# TRIGGER — directly commands a model, optionally conditionally
# --------------------------------------------------------------------------- #
class TriggerCondition(_SynapseModel):
    # "IMMEDIATE" means run now; otherwise the name of an event to wait for.
    on_event: str = Field(default="IMMEDIATE", alias="On-Event")
    source_uid: str | None = Field(default=None, alias="Source-UID")


class TriggerBody(_SynapseModel):
    target_uid: str = Field(alias="Target-UID")
    condition: TriggerCondition = Field(
        default_factory=TriggerCondition, alias="Condition"
    )
    action_to_trigger: str = Field(alias="Action-To-Trigger")
    parameters: dict[str, Any] = Field(default_factory=dict, alias="Parameters")


# --------------------------------------------------------------------------- #
# STATE_CHANGE — reports operational status (the handshake & the Diagnostician)
# --------------------------------------------------------------------------- #
class StateChangeBody(_SynapseModel):
    target_uid: str = Field(alias="Target-UID")
    status_code: str = Field(alias="Status-Code")
    reason: str = Field(default="", alias="Reason")


SynapseBody = Union[EventBody, TriggerBody, StateChangeBody]


class SynapseMessage(_SynapseModel):
    """A complete Synapse message: Header + a type-specific Body."""

    header: SynapseHeader = Field(alias="Header")
    body: SynapseBody = Field(alias="Body")

    @property
    def type(self) -> MessageType:
        return self.header.message_type

    @property
    def source(self) -> str:
        return self.header.source_uid

    def to_wire(self) -> dict[str, Any]:
        """Serialize to the exact spec field names (hyphenated)."""
        return self.model_dump(by_alias=True, mode="json")


# --------------------------------------------------------------------------- #
# Factory helpers — build well-formed messages without juggling the envelope
# --------------------------------------------------------------------------- #
def make_event(
    *,
    source_uid: str,
    event_name: str,
    data_asset_uid: str,
    description: str = "",
    confidence_score: float | None = None,
) -> SynapseMessage:
    return SynapseMessage(
        header=SynapseHeader(source_uid=source_uid, message_type=MessageType.EVENT),
        body=EventBody(
            event_name=event_name,
            payload=EventPayload(
                data_asset_uid=data_asset_uid,
                description=description,
                confidence_score=confidence_score,
            ),
        ),
    )


def make_trigger(
    *,
    source_uid: str,
    target_uid: str,
    action_to_trigger: str,
    on_event: str = "IMMEDIATE",
    condition_source_uid: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> SynapseMessage:
    return SynapseMessage(
        header=SynapseHeader(source_uid=source_uid, message_type=MessageType.TRIGGER),
        body=TriggerBody(
            target_uid=target_uid,
            condition=TriggerCondition(
                on_event=on_event, source_uid=condition_source_uid
            ),
            action_to_trigger=action_to_trigger,
            parameters=parameters or {},
        ),
    )


def make_state_change(
    *,
    source_uid: str,
    target_uid: str,
    status_code: str,
    reason: str = "",
) -> SynapseMessage:
    return SynapseMessage(
        header=SynapseHeader(
            source_uid=source_uid, message_type=MessageType.STATE_CHANGE
        ),
        body=StateChangeBody(
            target_uid=target_uid, status_code=status_code, reason=reason
        ),
    )
