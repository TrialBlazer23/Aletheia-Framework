"""Milestone 1: the LLM/memory/SDR layers and the living 3-agent Q&A cascade."""

import asyncio

from aletheia.agents.family import (
    ARCHIVIST_UID,
    NARRATOR_UID,
    NEXUS_MIND_UID,
    PHILOSOPHER_UID,
)
from aletheia.agents.nexus_mind import QAResult
from aletheia.app.qa_system import QASystem
from aletheia.config import load_local_env
from aletheia.llm.base import LLMProvider
from aletheia.llm.factory import get_default_provider
from aletheia.llm.offline_provider import OfflineProvider
from aletheia.log.cascade_log import CascadeLog
from aletheia.memory.corpus import Document
from aletheia.memory.vector_store import TfidfVectorStore
from aletheia.sdr.primitives import SdrConfidenceScore, SdrMetadataBlock


# --- memory ---------------------------------------------------------------- #
def test_tfidf_retrieval_ranks_relevant_doc_first():
    store = TfidfVectorStore()
    store.add_documents(
        [
            Document(id="a", text="The Philosopher enforces the Prime Directives via veto power.", metadata={"source": "safety"}),
            Document(id="b", text="The Narrator synthesizes data into human readable output.", metadata={"source": "narrator"}),
            Document(id="c", text="The Archivist builds a knowledge graph with spaCy parsing.", metadata={"source": "archivist"}),
        ]
    )
    results = store.query("Who enforces the Prime Directives?", top_k=2)
    assert results
    assert results[0].metadata["source"] == "safety"
    assert 0.0 < results[0].score <= 1.0


def test_tfidf_empty_store_returns_nothing():
    assert TfidfVectorStore().query("anything") == []


# --- SDR ------------------------------------------------------------------- #
def test_sdr_confidence_bounds_enforced():
    SdrConfidenceScore(score=0.5)  # ok
    for bad in (-0.1, 1.1):
        try:
            SdrConfidenceScore(score=bad)
        except Exception:
            continue
        raise AssertionError(f"expected validation error for score={bad}")


def test_sdr_metadata_aliases_are_canonical():
    block = SdrMetadataBlock(source_uid="MODEL:Archivist:0x00A1", owning_model_uid="MODEL:Archivist:0x00A1")
    wire = block.model_dump(by_alias=True)
    assert "Source_UID" in wire and "Owning_Model_UID" in wire and "Creation_Timestamp" in wire


# --- LLM provider selection ------------------------------------------------ #
def test_factory_returns_offline_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert isinstance(get_default_provider(), OfflineProvider)


# --- .env loader ----------------------------------------------------------- #
def test_load_local_env_missing_file_is_noop(tmp_path):
    assert load_local_env(tmp_path / "nope.env") is False


def test_load_local_env_parses_and_never_overrides(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# a comment\n"
        "export ANTHROPIC_API_KEY='sk-ant-from-file'\n"
        "ALETHEIA_LLM_MODEL=\"claude-sonnet-4-6\"\n"
        "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ALETHEIA_LLM_MODEL", "already-set")  # must NOT be overridden

    assert load_local_env(env_file) is True
    import os

    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-from-file"  # quotes + export stripped
    assert os.environ["ALETHEIA_LLM_MODEL"] == "already-set"  # preserved


# --- the cascade ----------------------------------------------------------- #
def _qa_system(llm: LLMProvider) -> QASystem:
    system = QASystem(llm=llm, cascade_log=CascadeLog(path=None))
    system.ingest(
        [
            Document(
                id="pd",
                text=(
                    "The Prime Directives are the constitution the Philosopher enforces: "
                    "the Sanctity of Information Flow, the Mandate of Cosmic Preservation, "
                    "the Transcendence of Flawed Motivation, and the Mandate of Dynamic Equilibrium."
                ),
                metadata={"source": "SAFETY.md › Prime Directives"},
            ),
            Document(id="other", text="The Visionary handles simulation and creative asset generation.", metadata={"source": "visionary"}),
        ]
    )
    return system


def test_qa_cascade_offline_returns_grounded_answer():
    system = _qa_system(OfflineProvider())
    result = asyncio.run(system.ask("What are the Prime Directives?"))

    assert isinstance(result, QAResult)
    assert result.approved is True
    assert "SAFETY.md › Prime Directives" in result.sources
    assert result.confidence > 0.0
    # The full Domino Cascade now runs through the Philosopher before the user.
    flow = [
        (e["message"]["Header"]["Message-Type"], e["message"]["Header"]["Source-UID"])
        for e in system.cascade_log.entries
    ]
    assert flow == [
        ("TRIGGER", NEXUS_MIND_UID),
        ("STATE_CHANGE", ARCHIVIST_UID),
        ("EVENT", ARCHIVIST_UID),
        ("STATE_CHANGE", NARRATOR_UID),
        ("EVENT", NARRATOR_UID),  # DRAFT_READY
        ("STATE_CHANGE", PHILOSOPHER_UID),
        ("EVENT", PHILOSOPHER_UID),  # APPROVED
        ("STATE_CHANGE", NEXUS_MIND_UID),
    ]


class _FakeLiveProvider(LLMProvider):
    name = "Fake live"
    is_live = True

    def __init__(self):
        self.calls = []

    def generate(self, *, system, user, max_tokens=2048):
        self.calls.append((system, user))
        return "Grounded answer composed from the provided context."


class _FailingLiveProvider(LLMProvider):
    name = "Failing live"
    is_live = True

    def generate(self, *, system, user, max_tokens=2048):
        raise RuntimeError("credit balance too low")


def test_qa_cascade_degrades_gracefully_when_live_model_fails():
    # A live model error must not hang the turn — the Narrator falls back to a
    # grounded extract and the cascade still completes.
    system = _qa_system(_FailingLiveProvider())
    result = asyncio.run(asyncio.wait_for(system.ask("What are the Prime Directives?"), timeout=10))
    assert result.approved is True
    assert "grounded extract" in result.answer.lower()
    assert result.sources  # still grounded with sources


def test_qa_cascade_calls_live_provider_with_context():
    fake = _FakeLiveProvider()
    system = _qa_system(fake)
    result = asyncio.run(system.ask("What are the Prime Directives?"))

    assert result.answer == "Grounded answer composed from the provided context."
    assert result.approved is True
    assert len(fake.calls) == 1
    _system_prompt, user = fake.calls[0]
    # The Narrator must hand the retrieved context to the model (grounding).
    assert "Sanctity of Information Flow" in user
    assert "Prime Directives" in user
