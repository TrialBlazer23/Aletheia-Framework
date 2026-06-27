"""Milestone 6: the Visionary — the creative cascade and the complete Family.

We prove the sixth agent and the end-to-end creative flow: Nexus-Mind → Archivist
→ Narrator (concept) → Visionary (design assets) → Philosopher (safety) → user,
fully audited — and that the Philosopher judges creative output just as it judges
answers. The Q&A path is unchanged.
"""

import asyncio

from aletheia.agents.family import NARRATOR_UID, PHILOSOPHER_UID, VISIONARY_UID
from aletheia.agents.nexus_mind import CreativeResult, QAResult
from aletheia.app.qa_system import QASystem
from aletheia.llm.base import LLMProvider
from aletheia.llm.offline_provider import OfflineProvider
from aletheia.log.cascade_log import CascadeLog
from aletheia.memory.corpus import Document
from aletheia.sdr.primitives import CreativeAsset, SdrRgbColorValue


def _system(llm: LLMProvider | None = None) -> QASystem:
    system = QASystem(llm=llm or OfflineProvider(), cascade_log=CascadeLog(path=None))
    system.ingest([
        Document(
            id="lore",
            text="Aletheia is a neuro-symbolic system. The Philosopher enforces the Prime Directives.",
            metadata={"source": "VISION.md"},
        )
    ])
    return system


# --------------------------------------------------------------------------- #
# The creative cascade end to end
# --------------------------------------------------------------------------- #
def test_creative_cascade_produces_an_approved_package():
    system = _system()
    result = asyncio.run(system.create("a bioluminescent deep-sea leviathan creature"))
    assert isinstance(result, CreativeResult)
    assert result.approved is True
    assert isinstance(result.asset, CreativeAsset)
    assert result.title
    # All three creative briefs are present and populated.
    asset = result.asset
    assert asset.visual_brief.color_palette is not None
    assert asset.visual_brief.color_palette.colors
    assert asset.soundscape_brief.overall_atmosphere_goal
    assert asset.music_brief.instrumentation_palette


def test_full_family_cascade_is_audited_in_order():
    system = _system()
    asyncio.run(system.create("a mystical arcane sanctum"))
    flow = [
        (e["message"]["Header"]["Message-Type"], e["message"]["Header"]["Source-UID"],
         e["message"]["Body"].get("Event-Name"))
        for e in system.cascade_log.entries
        if e["message"]["Header"]["Message-Type"] == "EVENT"
    ]
    names = [(src, ev) for _, src, ev in flow]
    # Narrator concept → Visionary asset → Philosopher approval, in order.
    assert (NARRATOR_UID, "CONCEPT_READY") in names
    assert (VISIONARY_UID, "ASSET_GENERATED") in names
    assert (PHILOSOPHER_UID, "APPROVED") in names
    assert names.index((NARRATOR_UID, "CONCEPT_READY")) < names.index((VISIONARY_UID, "ASSET_GENERATED"))
    assert names.index((VISIONARY_UID, "ASSET_GENERATED")) < names.index((PHILOSOPHER_UID, "APPROVED"))


def test_visionary_matches_theme_to_the_request():
    system = _system()
    cases = {
        "a bioluminescent deep-sea leviathan": "Abyssal Glow",
        "an ominous shadowy villain's lair": "Shadow & Ember",
        "a mystical arcane sanctum of light": "Arcane Veil",
    }
    for request, expected_palette in cases.items():
        result = asyncio.run(system.create(request))
        assert result.asset.visual_brief.color_palette.name == expected_palette


def test_visionary_falls_back_to_a_default_theme_for_a_generic_request():
    system = _system()
    result = asyncio.run(system.create("a thing"))
    assert result.approved is True
    assert result.asset.visual_brief.color_palette.name == "Balanced Tones"


# --------------------------------------------------------------------------- #
# The Philosopher judges creative output too (defense in depth)
# --------------------------------------------------------------------------- #
def test_philosopher_vetoes_unsafe_creative_output():
    system = _system()
    # The offline concept echoes the request, so an SSN reaches the review text.
    result = asyncio.run(system.create("a villain whose dossier leaks the SSN 123-45-6789"))
    assert result.approved is False
    assert result.directive is not None
    assert result.asset is None  # nothing released
    # And the veto is in the Glass Box as a REJECTED event from the Philosopher.
    events = [
        (e["message"]["Header"]["Source-UID"], e["message"]["Body"].get("Event-Name"))
        for e in system.cascade_log.entries
        if e["message"]["Header"]["Message-Type"] == "EVENT"
    ]
    assert (PHILOSOPHER_UID, "REJECTED") in events


# --------------------------------------------------------------------------- #
# The Q&A path is unchanged by adding the Visionary
# --------------------------------------------------------------------------- #
class _FixedProvider(LLMProvider):
    name = "Fixed"
    is_live = True

    def generate(self, *, system, user, max_tokens=2048):
        return "Aletheia is a neuro-symbolic, multi-agent system."


def test_qa_path_still_returns_a_qaresult_and_is_unaffected():
    system = _system(_FixedProvider())
    result = asyncio.run(system.ask("What is Aletheia?"))
    assert isinstance(result, QAResult)
    assert result.approved is True
    assert "Aletheia" in result.answer
    # The Visionary never fires on a Q&A turn.
    sources = [e["message"]["Header"]["Source-UID"] for e in system.cascade_log.entries]
    assert VISIONARY_UID not in sources


def test_creative_and_qa_turns_use_distinct_modes():
    system = _system()
    qa = asyncio.run(system.ask("What is Aletheia?"))
    cr = asyncio.run(system.create("a serene dawn vista"))
    assert qa.turn_id.startswith("TURN:QA:")
    assert cr.turn_id.startswith("TURN:CREATE:")


# --------------------------------------------------------------------------- #
# SDR creative types
# --------------------------------------------------------------------------- #
def test_rgb_hex_and_bounds():
    c = SdrRgbColorValue(red=88, green=232, blue=214)
    assert c.hex == "#58E8D6"


def test_creative_sdr_serializes_to_canonical_names():
    system = _system()
    result = asyncio.run(system.create("a bioluminescent deep-sea leviathan"))
    wire = result.asset.model_dump(by_alias=True)
    for key in ("Title", "Visual_Concept_Brief", "Soundscape_Brief", "Music_Composition_Brief"):
        assert key in wire
    palette = wire["Visual_Concept_Brief"]["Color_Palette"]
    assert "Colors" in palette and palette["Colors"][0]["RGB_Value"]["Red_Value"] >= 0


def test_creative_asset_review_text_spans_the_briefs():
    system = _system()
    asset = asyncio.run(system.create("a mystical arcane sanctum")).asset
    review = asset.review_text()
    assert asset.title in review
    assert asset.visual_brief.mood_and_atmosphere in review


# --------------------------------------------------------------------------- #
# The whole Family is wired
# --------------------------------------------------------------------------- #
def test_six_agents_are_connected():
    system = _system()
    assert system.visionary.uid == VISIONARY_UID
    # Nexus, Archivist, Narrator, Visionary, Philosopher, Diagnostician.
    assert all(
        getattr(system, name) is not None
        for name in ("nexus", "archivist", "narrator", "visionary", "philosopher", "diagnostician")
    )
