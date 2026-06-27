"""The Synapse Protocol field-name contract is the most important thing to lock
down: the hyphenated spec names (Message-ID, Source-UID, Event-Name, ...) must
survive serialization exactly, or every downstream consumer breaks.
"""

from aletheia.protocol import (
    MessageType,
    UID,
    make_event,
    make_state_change,
    make_trigger,
)
from aletheia.protocol.messages import SynapseMessage


def test_uid_roundtrip_and_validation():
    uid = UID.parse("MODEL:Archivist:0x00A1")
    assert uid.category == "MODEL"
    assert uid.type == "Archivist"
    assert uid.identifier == "0x00A1"
    assert str(uid) == "MODEL:Archivist:0x00A1"

    for bad in ["", "MODEL:Archivist", "a:b:c:d", "MODEL::0x1"]:
        try:
            UID.parse(bad)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad!r}")


def test_event_wire_field_names_are_exact():
    msg = make_event(
        source_uid="MODEL:Archivist:0x00A1",
        event_name="DATA_VALIDATED",
        data_asset_uid="ASSET:KNOWLEDGE_GRAPH:0xK1L2",
        description="kg built",
        confidence_score=0.98,
    )
    wire = msg.to_wire()
    # Header contract
    assert set(wire["Header"]) == {
        "Message-ID",
        "Source-UID",
        "Timestamp",
        "Message-Type",
        "Protocol-Ver",
    }
    assert wire["Header"]["Message-Type"] == "EVENT"
    assert wire["Header"]["Protocol-Ver"] == "2.0"
    assert wire["Header"]["Message-ID"].startswith("MSG:")
    # Body contract
    assert wire["Body"]["Event-Name"] == "DATA_VALIDATED"
    payload = wire["Body"]["Payload"]
    assert payload["Data-Asset-UID"] == "ASSET:KNOWLEDGE_GRAPH:0xK1L2"
    assert payload["Confidence-Score"] == 0.98


def test_trigger_wire_field_names_are_exact():
    msg = make_trigger(
        source_uid="MODEL:Nexus-Mind:0x0001",
        target_uid="MODEL:Archivist:0x00A1",
        action_to_trigger="ACQUIRE_DATA",
        parameters={"source_url": "..."},
    )
    body = msg.to_wire()["Body"]
    assert body["Target-UID"] == "MODEL:Archivist:0x00A1"
    assert body["Action-To-Trigger"] == "ACQUIRE_DATA"
    assert body["Condition"]["On-Event"] == "IMMEDIATE"
    assert body["Parameters"] == {"source_url": "..."}


def test_state_change_wire_field_names_are_exact():
    msg = make_state_change(
        source_uid="MODEL:Diagnostician:0x00E5",
        target_uid="MODEL:Visionary:0x00D4",
        status_code="CASCADE_PAUSED",
        reason="excessive resource usage",
    )
    body = msg.to_wire()["Body"]
    assert body["Target-UID"] == "MODEL:Visionary:0x00D4"
    assert body["Status-Code"] == "CASCADE_PAUSED"
    assert body["Reason"] == "excessive resource usage"


def test_message_json_roundtrip_preserves_contract():
    original = make_event(
        source_uid="MODEL:Narrator:0x00B2",
        event_name="DRAFT_READY",
        data_asset_uid="ASSET:DRAFT:0xD1",
    )
    # Reload from the exact wire form and confirm semantics survive.
    reloaded = SynapseMessage.model_validate(original.to_wire())
    assert reloaded.type == MessageType.EVENT
    assert reloaded.source == "MODEL:Narrator:0x00B2"
    assert reloaded.body.event_name == "DRAFT_READY"
