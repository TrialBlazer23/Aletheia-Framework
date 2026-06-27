"""Interest Profile matching + Listener relevance filtering."""

from aletheia.protocol.messages import (
    MessageType,
    make_event,
    make_state_change,
    make_trigger,
)
from aletheia.sil.interest_profile import InterestProfile, InterestRule
from aletheia.sil.listener import Listener

ARCHIVIST = "MODEL:Archivist:0x00A1"
NARRATOR = "MODEL:Narrator:0x00B2"
NEXUS = "MODEL:Nexus-Mind:0x0001"


def _narrator_listener() -> Listener:
    profile = InterestProfile(
        [
            InterestRule(
                action_to_trigger="GENERATE_NARRATIVE_DRAFT",
                source_model_uid=ARCHIVIST,
                message_type=MessageType.EVENT,
                event_name="DATA_VALIDATED",
            )
        ]
    )
    return Listener(NARRATOR, profile)


def test_listener_matches_subscribed_event():
    listener = _narrator_listener()
    msg = make_event(
        source_uid=ARCHIVIST,
        event_name="DATA_VALIDATED",
        data_asset_uid="ASSET:KG:0xK1",
        confidence_score=0.9,
    )
    relevant = listener.filter_relevant_messages(msg)
    assert relevant is not None
    assert relevant.action == "GENERATE_NARRATIVE_DRAFT"
    assert relevant.data["data_asset_uid"] == "ASSET:KG:0xK1"
    assert relevant.data["confidence_score"] == 0.9


def test_listener_ignores_non_matching_event_name():
    listener = _narrator_listener()
    msg = make_event(
        source_uid=ARCHIVIST, event_name="SOMETHING_ELSE", data_asset_uid="ASSET:X:0x1"
    )
    assert listener.filter_relevant_messages(msg) is None


def test_listener_ignores_wrong_source():
    listener = _narrator_listener()
    msg = make_event(
        source_uid=NEXUS, event_name="DATA_VALIDATED", data_asset_uid="ASSET:X:0x1"
    )
    assert listener.filter_relevant_messages(msg) is None


def test_trigger_addressed_to_owner_is_always_relevant():
    # Narrator has no matching profile rule for triggers, but a TRIGGER aimed at
    # its UID must still activate it.
    listener = _narrator_listener()
    msg = make_trigger(
        source_uid=NEXUS,
        target_uid=NARRATOR,
        action_to_trigger="GENERATE",
        parameters={"topic": "safety"},
    )
    relevant = listener.filter_relevant_messages(msg)
    assert relevant is not None
    assert relevant.action == "GENERATE"
    assert relevant.data["parameters"] == {"topic": "safety"}


def test_trigger_for_other_agent_is_ignored():
    listener = _narrator_listener()
    msg = make_trigger(
        source_uid=NEXUS, target_uid=ARCHIVIST, action_to_trigger="ACQUIRE_DATA"
    )
    assert listener.filter_relevant_messages(msg) is None


def test_agent_never_reacts_to_its_own_broadcast():
    listener = _narrator_listener()
    own = make_event(
        source_uid=NARRATOR, event_name="DATA_VALIDATED", data_asset_uid="ASSET:X:0x1"
    )
    assert listener.filter_relevant_messages(own) is None


def test_status_code_rule_matches_state_change():
    profile = InterestProfile(
        [
            InterestRule(
                action_to_trigger="PAUSE_CURRENT_TASK",
                message_type=MessageType.STATE_CHANGE,
                status_code="CASCADE_PAUSED",
            )
        ]
    )
    listener = Listener(NARRATOR, profile)
    msg = make_state_change(
        source_uid="MODEL:Diagnostician:0x00E5",
        target_uid=NARRATOR,
        status_code="CASCADE_PAUSED",
        reason="loop detected",
    )
    relevant = listener.filter_relevant_messages(msg)
    assert relevant is not None
    assert relevant.action == "PAUSE_CURRENT_TASK"


def test_interest_profile_from_dict():
    profile = InterestProfile.from_dict(
        {
            "listensFor": [
                {
                    "source_model_UID": ARCHIVIST,
                    "message_type": "EVENT",
                    "event_name": "DATA_VALIDATED",
                    "action_to_trigger": "GENERATE_NARRATIVE_DRAFT",
                }
            ]
        }
    )
    assert len(profile.rules) == 1
    assert profile.rules[0].source_model_uid == ARCHIVIST
    assert profile.rules[0].message_type == MessageType.EVENT
