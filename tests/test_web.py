"""The browser interface (FastAPI) — endpoints over the QASystem.

Skipped automatically where the optional ``web`` extra isn't installed
(``pip install -e ".[web]"``).
"""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from aletheia.app.qa_system import QASystem  # noqa: E402
from aletheia.llm.offline_provider import OfflineProvider  # noqa: E402
from aletheia.log.cascade_log import CascadeLog  # noqa: E402
from aletheia.web.app import create_app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    # Inject an OFFLINE system so the tests are fast and deterministic (no live
    # model calls). `with` triggers the lifespan, which ingests the docs once.
    system = QASystem(llm=OfflineProvider(), cascade_log=CascadeLog(path=None))
    with TestClient(create_app(system)) as c:
        yield c


def test_index_is_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "<title>Aletheia" in r.text


def test_health_reports_the_system(client):
    h = client.get("/api/health").json()
    assert h["directives"] == 4
    assert h["passages"] > 0
    assert "brain" in h


def test_ask_returns_an_answer_with_the_cascade(client):
    d = client.post("/api/ask", json={"text": "What does the Philosopher enforce?"}).json()
    assert d["kind"] == "qa"
    assert d["approved"] is True
    assert isinstance(d["answer"], str) and d["answer"]
    # The Glass Box: the response carries the Domino Cascade hops.
    assert d["cascade"] and all({"seq", "type", "source", "label"} <= set(h) for h in d["cascade"])


def test_create_returns_a_design_package_with_swatches(client):
    d = client.post("/api/create", json={"text": "a bioluminescent deep-sea creature"}).json()
    assert d["kind"] == "creative" and d["approved"] is True
    assert d["palette"]["name"] == "Abyssal Glow"
    assert all(c["hex"].startswith("#") for c in d["palette"]["colors"])
    # The creative cascade ran the Visionary.
    assert "Visionary" in [h["source"] for h in d["cascade"]]


def test_create_unsafe_output_is_vetoed(client):
    d = client.post("/api/create", json={"text": "a villain dossier leaking SSN 123-45-6789"}).json()
    assert d["approved"] is False
    assert d["directive"]


def test_empty_input_is_rejected(client):
    assert client.post("/api/ask", json={"text": "   "}).status_code == 400
