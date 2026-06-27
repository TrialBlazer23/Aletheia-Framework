"""FastAPI app exposing the Aletheia ``QASystem`` over HTTP.

One shared system is built at startup (its docs ingested once); requests are
serialized with a lock so the shared Cascade Log can be sliced cleanly per turn
— enough for a personal demo without touching the agents. Every response carries
the cascade (the Glass Box hops) so the UI can show the Family at work.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from aletheia.app.qa_system import QASystem

_STATIC = Path(__file__).resolve().parent / "static"


class _Prompt(BaseModel):
    text: str = ""


def _short(uid: str) -> str:
    """``MODEL:Narrator:0x00B2`` → ``Narrator``; pass other ids through."""
    parts = uid.split(":")
    return parts[1] if len(parts) == 3 else uid


def _cascade_slice(system: QASystem, start: int) -> list[dict[str, Any]]:
    """The Cascade-Log entries produced since ``start`` (one turn's hops)."""
    hops = []
    for rec in system.cascade_log.entries[start:]:
        msg = rec["message"]
        header, body = msg["Header"], msg["Body"]
        mtype = header["Message-Type"]
        label = body.get("Event-Name") or body.get("Action-To-Trigger") or body.get("Status-Code")
        hops.append({
            "seq": rec["seq"],
            "type": mtype,
            "source": _short(header["Source-UID"]),
            "label": label,
        })
    return hops


def _qa_payload(result, cascade) -> dict[str, Any]:
    return {
        "kind": "qa",
        "approved": result.approved,
        "answer": result.answer,
        "sources": list(dict.fromkeys(result.sources)),
        "confidence": round(result.confidence, 3),
        "directive": result.directive,
        "reason": result.reason,
        "cascade": cascade,
    }


def _creative_payload(result, cascade) -> dict[str, Any]:
    if not result.approved or result.asset is None:
        return {
            "kind": "creative", "approved": False, "directive": result.directive,
            "reason": result.reason, "cascade": cascade,
        }
    a = result.asset
    vb, sb, mb = a.visual_brief, a.soundscape_brief, a.music_brief
    pal = vb.color_palette
    return {
        "kind": "creative",
        "approved": True,
        "title": a.title,
        "concept": a.concept.text,
        "art_direction": vb.subject_description.text,
        "mood": vb.mood_and_atmosphere,
        "styles": vb.visual_styles,
        "key_elements": vb.key_elements,
        "palette": {
            "name": pal.name if pal else "",
            "harmony": pal.harmony_rule if pal else "",
            "colors": [
                {"name": c.name, "hex": c.rgb.hex, "role": c.role}
                for c in (pal.colors if pal else [])
            ],
        },
        "soundscape": {
            "atmosphere": sb.overall_atmosphere_goal,
            "ambient": sb.ambient_noise_profile,
            "effects": sb.key_sound_effects,
        },
        "music": {
            "genre": mb.genre_style_suggestions,
            "tempo": mb.tempo_description,
            "key": mb.key_modality,
            "instruments": mb.instrumentation_palette,
            "arc": mb.emotional_arc_target,
        },
        "sources": list(dict.fromkeys(result.sources))[:4],
        "confidence": round(result.confidence, 3),
        "cascade": cascade,
    }


def create_app(system: QASystem | None = None) -> "FastAPI":  # noqa: F821
    """Build the FastAPI app.

    ``system`` lets tests inject a pre-configured (e.g. offline) ``QASystem`` so
    they don't call the live model; in normal use it's left ``None`` and a default
    system is built (live Claude if a key is set). Either way it's ingested once
    at startup.
    """
    from fastapi import FastAPI
    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles

    state: dict[str, Any] = {}

    @asynccontextmanager
    async def lifespan(app):
        sys = system if system is not None else QASystem()
        n = sys.ingest_own_docs()
        state["system"] = sys
        state["lock"] = asyncio.Lock()
        state["ingested"] = n
        yield

    app = FastAPI(title="Aletheia", lifespan=lifespan)

    async def _run_turn(kind: str, text: str) -> dict[str, Any]:
        system: QASystem = state["system"]
        async with state["lock"]:
            start = len(system.cascade_log.entries)
            if kind == "create":
                result = await system.create(text)
                cascade = _cascade_slice(system, start)
                return _creative_payload(result, cascade)
            result = await system.ask(text)
            cascade = _cascade_slice(system, start)
            return _qa_payload(result, cascade)

    @app.post("/api/ask")
    async def ask(prompt: _Prompt):
        if not prompt.text.strip():
            return JSONResponse({"error": "Please enter a question."}, status_code=400)
        return await _run_turn("ask", prompt.text.strip())

    @app.post("/api/create")
    async def create(prompt: _Prompt):
        if not prompt.text.strip():
            return JSONResponse({"error": "Please enter a creative brief."}, status_code=400)
        return await _run_turn("create", prompt.text.strip())

    @app.get("/api/health")
    async def health():
        system: QASystem = state["system"]
        h = system.diagnostician.health_report()
        return {
            "brain": system.llm.name,
            "live": system.llm.is_live,
            "passages": state.get("ingested", 0),
            "graph_entities": system.graph.num_entities if system.graph else 0,
            "graph_facts": system.graph.num_facts if system.graph else 0,
            "extractor": system.extractor.name if system.extractor else "none",
            "policy_version": system.policy.version,
            "directives": len(system.philosopher.directives.directives),
            "cascades_tracked": h["cascades_tracked"],
            "anomalies": h["anomalies"],
            "breaker_tripped": h["breaker_tripped"],
        }

    @app.get("/")
    async def index():
        return FileResponse(_STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=_STATIC), name="static")
    return app


# A module-level app so `uvicorn aletheia.web.app:app` also works.
try:  # pragma: no cover - import guard
    app = create_app()
except Exception:  # fastapi not installed — `python main.py --web` will explain.
    app = None


def run(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Start the dev server (used by ``python main.py --web``)."""
    try:
        import uvicorn
    except ModuleNotFoundError:
        print(
            "The web interface needs FastAPI + uvicorn. Install them with:\n"
            '  pip install -e ".[web]"\n'
            "then run  python main.py --web  again."
        )
        return
    print(f"\n  Aletheia web UI → http://localhost:{port}\n  (Ctrl-C to stop)\n")
    uvicorn.run(create_app(), host=host, port=port)
