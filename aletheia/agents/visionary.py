"""The Visionary (0x00D4) — simulation / creative (Milestone 6, the last agent).

"The Visionary transforms narrative concepts into visual and auditory
aesthetics." Its Listener is tuned to the Narrator's ``CONCEPT_READY`` event; on
firing it turns that grounded concept into a bundle of structured **design
briefs** — a visual concept brief (with a color palette), a soundscape brief, and
a music composition brief — and broadcasts ``EVENT: ASSET_GENERATED``. The
Philosopher still validates the result before it reaches the user: generation is
separated from judgment here too.

Generation is *deterministic by default* (a curated theme→design mapping, so the
system runs offline and tests are reproducible) and **enriched by Claude when a
live model is available** (richer art direction), degrading gracefully back to
the template if the model errors — the same posture as the Narrator. A real
image/audio model could later slot in behind the same agent without changing the
cascade; today the Visionary produces the briefs that would drive it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aletheia.agents.family import NARRATOR_UID, VISIONARY_UID
from aletheia.agents.family_member import FamilyMember
from aletheia.bus.base import MessageBus
from aletheia.llm.base import LLMProvider
from aletheia.memory.asset_store import AssetStore
from aletheia.protocol.messages import MessageType, SynapseMessage
from aletheia.sdr.primitives import (
    ConceptAsset,
    CreativeAsset,
    SdrColorDefinition,
    SdrColorPaletteDefinition,
    SdrConfidenceScore,
    SdrMetadataBlock,
    SdrMusicCompositionBrief,
    SdrRgbColorValue,
    SdrSoundscapeBrief,
    SdrTextBlock,
    SdrVisualConceptBrief,
)
from aletheia.sil.interest_profile import InterestProfile, InterestRule

_ART_DIRECTION_PROMPT = (
    "You are the Visionary of the Aletheia system, an art director. Given a grounded "
    "creative concept, write 2-3 vivid sentences of visual art direction describing how it "
    "should look — form, texture, light, silhouette. Be evocative and concrete. Do NOT add "
    "facts about the world; only describe the visual realization of the given concept."
)


@dataclass(frozen=True)
class _Theme:
    """A curated design theme: palette + sound + music for a mood family."""

    name: str
    keywords: tuple[str, ...]
    palette_name: str
    harmony: str
    colors: tuple[tuple[str, int, int, int, str], ...]  # (name, r, g, b, role)
    styles: tuple[str, ...]
    mood: str
    motifs: tuple[str, ...]
    ambient: str
    sound_effects: tuple[str, ...]
    genre: tuple[str, ...]
    tempo: str
    key_modality: str
    instrumentation: tuple[str, ...]
    emotional_arc: str


# A small, curated atlas. Each theme is deterministic and self-consistent.
_THEMES: tuple[_Theme, ...] = (
    _Theme(
        name="truth/light",
        keywords=("truth", "light", "clarity", "reveal", "un-concealment", "luminous", "dawn", "illuminat"),
        palette_name="Aletheia Dawn",
        harmony="Analogous (warm light)",
        colors=(("Luminous White", 245, 246, 240, "primary"), ("Solar Gold", 232, 188, 76, "primary"),
                ("Clear Cyan", 96, 198, 214, "accent"), ("Slate Neutral", 64, 70, 82, "neutral")),
        styles=("Luminous realism", "Soft volumetric light", "Hopeful sci-fi"),
        mood="Revelatory, serene, hopeful",
        motifs=("breaking light", "unveiling", "clean geometry", "open horizon"),
        ambient="A high, clear tone rising over soft wind; distant resonant chimes.",
        sound_effects=("a soft chime as light breaks", "a deep harmonic swell"),
        genre=("Orchestral ambient", "Cinematic post-rock"),
        tempo="Slow and building (~70 BPM)",
        key_modality="C major (Lydian color)",
        instrumentation=("Strings", "Glass harmonica", "Soft choir", "Sub-bass swell"),
        emotional_arc="From quiet uncertainty to luminous clarity.",
    ),
    _Theme(
        name="deep-sea/abyss",
        keywords=("deep-sea", "deep sea", "ocean", "abyss", "leviathan", "bioluminescent", "marine", "aquatic", "creature", "trench"),
        palette_name="Abyssal Glow",
        harmony="Complementary (abyss + glow)",
        colors=(("Abyss Black-Blue", 8, 18, 34, "primary"), ("Deep Teal", 18, 66, 78, "primary"),
                ("Bioluminescent Cyan", 88, 232, 214, "accent"), ("Pale Silt", 142, 150, 150, "neutral")),
        styles=("Dark bioluminescent realism", "Concept-art rendering", "Volumetric underwater light"),
        mood="Mysterious, vast, quietly awe-inspiring",
        motifs=("glowing photophores", "slow drifting silhouette", "shafts of dim light", "pressure and depth"),
        ambient="Low oceanic pressure rumble, sparse distant clicks and groans.",
        sound_effects=("a deep whale-like call", "a soft pulse as bioluminescence flares"),
        genre=("Dark ambient", "Cinematic drone"),
        tempo="Very slow, tidal (~50 BPM)",
        key_modality="D minor (Dorian)",
        instrumentation=("Sub-bass", "Bowed metal", "Processed whale song", "Sparse piano"),
        emotional_arc="From stillness to a vast, humbling encounter.",
    ),
    _Theme(
        name="ominous/shadow",
        keywords=("ominous", "dark", "shadow", "dread", "menacing", "villain", "corrupt", "fear", "threat"),
        palette_name="Shadow & Ember",
        harmony="Split-complementary (dark + ember)",
        colors=(("Void Black", 18, 16, 20, "primary"), ("Deep Crimson", 120, 24, 36, "primary"),
                ("Ember Orange", 214, 96, 40, "accent"), ("Ash Grey", 88, 84, 88, "neutral")),
        styles=("Chiaroscuro", "Gritty realism", "High-contrast"),
        mood="Ominous, tense, foreboding",
        motifs=("long shadows", "single ember light", "jagged silhouette", "encroaching dark"),
        ambient="A low dissonant drone with distant, irregular impacts.",
        sound_effects=("a sudden low hit", "a scraping metallic groan"),
        genre=("Dark orchestral", "Industrial ambient"),
        tempo="Slow, heavy (~60 BPM)",
        key_modality="C minor (Phrygian)",
        instrumentation=("Low brass", "Detuned strings", "Percussive metal", "Sub-drone"),
        emotional_arc="From unease to dread.",
    ),
    _Theme(
        name="mystical/arcane",
        keywords=("mystical", "arcane", "magic", "ethereal", "ancient", "rune", "spirit", "dream", "celestial"),
        palette_name="Arcane Veil",
        harmony="Triadic (violet/teal/silver)",
        colors=(("Deep Violet", 64, 40, 110, "primary"), ("Arcane Teal", 36, 132, 130, "primary"),
                ("Moon Silver", 206, 212, 224, "accent"), ("Dusk Indigo", 40, 44, 78, "neutral")),
        styles=("Ethereal illustration", "Painterly fantasy", "Soft glow"),
        mood="Mystical, wondrous, otherworldly",
        motifs=("floating motes", "glowing glyphs", "soft mist", "impossible geometry"),
        ambient="Shimmering pads over a soft, reverberant hum; faint distant bells.",
        sound_effects=("a crystalline shimmer", "a soft arcane resonance"),
        genre=("Ethereal ambient", "Neoclassical"),
        tempo="Flowing, unhurried (~64 BPM)",
        key_modality="A minor (Aeolian, modal)",
        instrumentation=("Harp", "Celesta", "Airy choir", "Bowed glass"),
        emotional_arc="From curiosity to quiet wonder.",
    ),
)

_DEFAULT_THEME = _Theme(
    name="balanced",
    keywords=(),
    palette_name="Balanced Tones",
    harmony="Neutral balance",
    colors=(("Warm White", 236, 232, 224, "primary"), ("Muted Teal", 70, 120, 124, "primary"),
            ("Amber Accent", 210, 158, 84, "accent"), ("Stone Grey", 96, 98, 100, "neutral")),
    styles=("Grounded realism", "Clean composition"),
    mood="Balanced, considered",
    motifs=("clear focal point", "natural light"),
    ambient="A neutral room tone with soft, even presence.",
    sound_effects=("a gentle establishing tone",),
    genre=("Cinematic underscore",),
    tempo="Moderate (~90 BPM)",
    key_modality="G major",
    instrumentation=("Piano", "Strings", "Light percussion"),
    emotional_arc="A steady, grounded mood.",
)


def _visionary_profile() -> InterestProfile:
    return InterestProfile(
        [
            InterestRule(
                action_to_trigger="GENERATE_CREATIVE_ASSET",
                source_model_uid=NARRATOR_UID,
                message_type=MessageType.EVENT,
                event_name="CONCEPT_READY",
            )
        ]
    )


class Visionary(FamilyMember):
    def __init__(self, *, bus: MessageBus, llm: LLMProvider, asset_store: AssetStore) -> None:
        super().__init__(
            name="Visionary", uid=VISIONARY_UID, bus=bus, interest_profile=_visionary_profile()
        )
        self._llm = llm
        self._assets = asset_store

    async def handle_action(
        self, action: str, data: dict[str, Any], message: SynapseMessage
    ) -> None:
        if action != "GENERATE_CREATIVE_ASSET":
            return
        concept: ConceptAsset = self._assets.get(data["data_asset_uid"])

        # Match the design theme on the user's request — their clearest, most
        # stable intent (the generated concept is deliberately Aletheia-flavoured,
        # so matching on it would bias every brief toward the "truth/light" theme).
        theme = self._match_theme(concept.request)
        palette = self._palette(theme)
        art_direction = self._art_direction(concept, theme)
        title = self._title(concept.request)

        visual = SdrVisualConceptBrief(
            title=title,
            subject_description=SdrTextBlock(text=art_direction),
            visual_styles=list(theme.styles),
            color_palette=palette,
            mood_and_atmosphere=theme.mood,
            key_elements=self._key_elements(concept, theme),
            things_to_avoid=["generic stock imagery", "clichéd symbolism", "incoherent anatomy"],
            intended_usage="Concept art / pre-visualization reference",
        )
        soundscape = SdrSoundscapeBrief(
            overall_atmosphere_goal=theme.mood,
            ambient_noise_profile=theme.ambient,
            key_sound_effects=list(theme.sound_effects),
            musical_integration_notes="Music and ambience share the key/modality below; duck ambience under musical swells.",
            technical_delivery_specs="Stereo, adaptive looping",
        )
        music = SdrMusicCompositionBrief(
            title_or_purpose=f"{title} — theme",
            genre_style_suggestions=list(theme.genre),
            tempo_description=theme.tempo,
            key_modality=theme.key_modality,
            instrumentation_palette=list(theme.instrumentation),
            emotional_arc_target=theme.emotional_arc,
            estimated_duration="~90 seconds (loopable)",
        )

        creative = CreativeAsset(
            turn_id=concept.turn_id,
            request=concept.request,
            title=title,
            concept=SdrTextBlock(text=concept.concept.text),
            visual_brief=visual,
            soundscape_brief=soundscape,
            music_brief=music,
            sources=list(concept.sources),
            confidence=SdrConfidenceScore(score=concept.confidence.score),
            metadata=SdrMetadataBlock(source_uid=self.uid, owning_model_uid=self.uid),
        )
        self._assets.put(creative.synapse_uid, creative)

        # (Step 4) broadcast the result; the Philosopher validates it before release.
        await self.broadcaster.broadcast_event(
            event_name="ASSET_GENERATED",
            data_asset_uid=creative.synapse_uid,
            description=f"Creative package '{title}' generated ({theme.name} theme).",
            confidence_score=creative.confidence.score,
        )

    # --- generation helpers ------------------------------------------------ #
    @staticmethod
    def _match_theme(text: str) -> _Theme:
        low = text.lower()
        best, best_hits = _DEFAULT_THEME, 0
        for theme in _THEMES:
            hits = sum(1 for kw in theme.keywords if kw in low)
            if hits > best_hits:
                best, best_hits = theme, hits
        return best

    @staticmethod
    def _palette(theme: _Theme) -> SdrColorPaletteDefinition:
        return SdrColorPaletteDefinition(
            name=theme.palette_name,
            description=f"Palette evoking: {theme.mood}.",
            harmony_rule=theme.harmony,
            colors=[
                SdrColorDefinition(
                    name=name, role=role,
                    rgb=SdrRgbColorValue(red=r, green=g, blue=b),
                )
                for (name, r, g, b, role) in theme.colors
            ],
        )

    def _art_direction(self, concept: ConceptAsset, theme: _Theme) -> str:
        template = (
            f"Render the concept in a {theme.styles[0].lower()} style. "
            f"Lead with {theme.motifs[0]} and {theme.motifs[1] if len(theme.motifs) > 1 else 'a clear focal point'}; "
            f"hold an overall mood of {theme.mood.lower()}."
        )
        if not self._llm.is_live:
            return template
        try:
            user = (
                f"Concept to realize visually:\n{concept.concept.text}\n\n"
                f"Theme/mood: {theme.mood}. Motifs: {', '.join(theme.motifs)}."
            )
            text = self._llm.generate(system=_ART_DIRECTION_PROMPT, user=user, max_tokens=300)
            return text.strip() or template
        except Exception as exc:  # noqa: BLE001 — degrade, never hang the cascade
            print(
                f"[aletheia] Visionary: live model call failed ({type(exc).__name__}); "
                "using template art direction."
            )
            return template

    @staticmethod
    def _title(request: str) -> str:
        words = [w for w in request.replace("\n", " ").split() if w.isalpha()]
        # A short evocative title from the request's notable words.
        notable = [w.capitalize() for w in words if len(w) > 3][:3]
        return " ".join(notable) or "Untitled Concept"

    @staticmethod
    def _key_elements(concept: ConceptAsset, theme: _Theme) -> list[str]:
        elements = list(theme.motifs[:3])
        # Add a couple of grounded sources as canon-consistency anchors.
        if concept.sources:
            elements.append(f"consistent with canon ({concept.sources[0]})")
        return elements
