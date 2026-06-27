"""Milestone 6 proof: the Visionary — the sixth and final Family member.

Runs the creative cascade end to end and shows the whole Family working together:

    Nexus-Mind → Archivist (ground it in canon) → Narrator (a concept) →
    Visionary (design assets) → Philosopher (safety) → you.

For a creative request — "concept art for a new creature" — the Visionary
produces a structured design package: a visual concept brief with a color
palette, a soundscape brief, and a music composition brief. Generation is
deterministic offline (so it always runs) and enriched by Claude when a key is
set. The Philosopher still validates the result before release.

Run with ``python main.py --creative`` (or ``python -m
aletheia.demo.creative_demo``).
"""

from __future__ import annotations

import asyncio

from aletheia.app.qa_system import QASystem
from aletheia.log.cascade_log import CascadeLog

_REQUEST = (
    "Concept art for a new creature native to Aletheia's world: a bioluminescent "
    "deep-sea leviathan that embodies the principle of un-concealment — truth brought to light."
)


def _rule(title: str) -> None:
    print("\n" + "─" * 78)
    print(title)
    print("─" * 78)


async def run() -> None:
    print("\n=== Milestone 6 — the Visionary (the creative cascade) ===")
    system = QASystem(cascade_log=CascadeLog(path=None))
    n = system.ingest_own_docs()
    print(f"\nIngested {n} passages of Aletheia's own canon. Narrator/Visionary brain: {system.llm.name}.")
    print(f"Request:\n  {_REQUEST}")

    result = await system.create(_REQUEST)

    _rule("The Domino Cascade (the whole Family, audited)")
    for entry in system.cascade_log.entries:
        h, b = entry["message"]["Header"], entry["message"]["Body"]
        label = b.get("Event-Name") or b.get("Action-To-Trigger") or b.get("Status-Code")
        print(f"  [{entry['seq']:>2}] {h['Message-Type']:<12} {h['Source-UID']:<26} {label}")

    if not result.approved:
        _rule("Result: VETOED by the Philosopher")
        print(f"  directive: {result.directive}\n  reason: {result.reason}")
        return

    asset = result.asset
    vb = asset.visual_brief
    _rule(f"The generated creative package — '{asset.title}'")
    print(f"\n  CONCEPT (Narrator):\n    {asset.concept.text.strip()}")
    print(f"\n  ART DIRECTION (Visionary):\n    {vb.subject_description.text.strip()}")
    print(f"\n  VISUAL CONCEPT BRIEF")
    print(f"    mood    : {vb.mood_and_atmosphere}")
    print(f"    styles  : {', '.join(vb.visual_styles)}")
    print(f"    include : {', '.join(vb.key_elements)}")
    print(f"    avoid   : {', '.join(vb.things_to_avoid)}")
    pal = vb.color_palette
    print(f"\n  COLOR PALETTE — {pal.name}  ({pal.harmony_rule})")
    for c in pal.colors:
        print(f"    {c.rgb.hex}  {c.name:24} [{c.role}]")
    sb = asset.soundscape_brief
    print(f"\n  SOUNDSCAPE BRIEF")
    print(f"    atmosphere : {sb.overall_atmosphere_goal}")
    print(f"    ambient    : {sb.ambient_noise_profile}")
    print(f"    key fx     : {', '.join(sb.key_sound_effects)}")
    mb = asset.music_brief
    print(f"\n  MUSIC COMPOSITION BRIEF")
    print(f"    genre  : {', '.join(mb.genre_style_suggestions)}")
    print(f"    tempo  : {mb.tempo_description}    key: {mb.key_modality}")
    print(f"    instr  : {', '.join(mb.instrumentation_palette)}")
    print(f"    arc    : {mb.emotional_arc_target}")

    _rule("Verdict")
    print(f"  ✓ approved by the Philosopher   confidence: {result.confidence:.2f}")
    if result.sources:
        print(f"  grounded in canon: {', '.join(list(dict.fromkeys(result.sources))[:3])}")


def main() -> None:
    asyncio.run(run())
    print(
        "\nThe full six-agent Family produced a safety-checked creative asset, fully "
        "audited end to end. The Family is complete.\n"
    )


if __name__ == "__main__":
    main()
