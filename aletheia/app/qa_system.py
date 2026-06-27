"""``QASystem`` — assembles the Family into a question-answering system.

Nexus-Mind → Archivist → Narrator → Philosopher, watched by the Diagnostician,
grounded in a corpus (by default Aletheia's own design docs), with every message
recorded in the Cascade Log. One object you can ``await system.ask("...")``
against. Milestone 4 gives the Archivist a knowledge graph alongside its vectors,
so retrieval is hybrid (vector passages + traversed, cited facts).
"""

from __future__ import annotations

from pathlib import Path

from aletheia.agents.archivist import Archivist
from aletheia.agents.diagnostician import Diagnostician
from aletheia.agents.narrator import Narrator
from aletheia.agents.nexus_mind import CreativeResult, NexusMind, QAResult
from aletheia.agents.philosopher import Philosopher
from aletheia.agents.visionary import Visionary
from aletheia.bus.in_process import InProcessBus
from aletheia.config import load_local_env
from aletheia.diagnostics.circuit_breaker import CircuitBreaker
from aletheia.llm.base import LLMProvider
from aletheia.llm.factory import get_default_provider
from aletheia.log.cascade_log import CascadeLog
from aletheia.memory.asset_store import AssetStore
from aletheia.memory.corpus import Document, load_markdown_corpus
from aletheia.memory.extractor import KnowledgeExtractor, get_default_extractor
from aletheia.memory.graph_store import GraphStore, get_default_graph_store
from aletheia.memory.vector_store import TfidfVectorStore, VectorStore
from aletheia.resonance.analytics import Feedback, PerformanceAnalyzer
from aletheia.resonance.engine import (
    CallbackGavel,
    HumanGavel,
    ResonanceEngine,
    ResonanceOutcome,
)
from aletheia.resonance.policy import PolicyStore
from aletheia.resonance.sandbox import ResonanceSandbox
from aletheia.sdr.primitives import (
    AnswerAsset,
    RetrievedContextAsset,
    SdrEthicalAnalysisReport,
)

# The repository root — used to ingest Aletheia's own docs as the default corpus.
_REPO_ROOT = Path(__file__).resolve().parents[2]


class QASystem:
    def __init__(
        self,
        *,
        llm: LLMProvider | None = None,
        vector_store: VectorStore | None = None,
        cascade_log: CascadeLog | None = None,
        graph_store: GraphStore | None = None,
        extractor: KnowledgeExtractor | None = None,
        use_graph: bool = True,
        policy_store: PolicyStore | None = None,
        gavel: HumanGavel | None = None,
    ) -> None:
        self.cascade_log = cascade_log or CascadeLog(path="cascade_log.jsonl")
        # The circuit breaker the Diagnostician trips; the bus consults it.
        self.circuit_breaker = CircuitBreaker()
        self.bus = InProcessBus(
            cascade_log=self.cascade_log, circuit_breaker=self.circuit_breaker
        )
        self.assets = AssetStore()
        # Pick up a key from a local .env file (no-op if absent) before choosing
        # the provider. An explicitly-passed llm skips provider selection entirely.
        if llm is None:
            load_local_env()
        self.llm = llm or get_default_provider()
        self.vectors = vector_store or TfidfVectorStore()
        # The knowledge graph (Milestone 4). Defaults on, but degrades gracefully:
        # if NetworkX/spaCy aren't installed, the graph is None and the Archivist
        # runs vector-only. ``use_graph=False`` opts out (e.g. for speed in tests).
        if use_graph:
            self.graph = graph_store if graph_store is not None else get_default_graph_store()
            self.extractor = extractor or (get_default_extractor() if self.graph else None)
        else:
            self.graph = None
            self.extractor = None

        # The versioned operational policy the Resonance Cycle tunes (and that the
        # Archivist obeys at retrieval time). In-memory by default for tests/demos.
        self.policy = policy_store or PolicyStore(path=None)

        self.nexus = NexusMind(bus=self.bus, asset_store=self.assets)
        self.archivist = Archivist(
            bus=self.bus,
            vector_store=self.vectors,
            asset_store=self.assets,
            graph_store=self.graph,
            extractor=self.extractor,
            policy_store=self.policy,
        )
        self.narrator = Narrator(bus=self.bus, llm=self.llm, asset_store=self.assets)
        # The Visionary turns a Narrator concept into creative design assets (the
        # creative cascade). Generation only — the Philosopher still judges it.
        self.visionary = Visionary(bus=self.bus, llm=self.llm, asset_store=self.assets)
        # The Philosopher sits between generation and the user, with veto power
        # over BOTH Q&A answers and creative assets.
        self.philosopher = Philosopher(bus=self.bus, asset_store=self.assets)
        # The Diagnostician watches the whole bus, building CHOREOGRAPHY_LOG
        # telemetry for every turn and standing ready to trip the breaker on a
        # runaway. It is a passive observer in the healthy path — it adds no
        # traffic to a normal cascade, so it never perturbs the flow it measures.
        self.diagnostician = Diagnostician(
            bus=self.bus, asset_store=self.assets, circuit_breaker=self.circuit_breaker
        )
        for agent in (
            self.nexus,
            self.archivist,
            self.narrator,
            self.visionary,
            self.philosopher,
            self.diagnostician,
        ):
            agent.connect()

        # The Resonance Cycle (Milestone 5): supervised self-improvement. The
        # sandbox probes the Archivist read-only under a candidate policy; the
        # Philosopher verifies; the Human Gavel approves (default: a callback that
        # *denies* — nothing self-modifies without an explicit yes).
        self.analyzer = PerformanceAnalyzer()
        self.sandbox = ResonanceSandbox(self.archivist.retrieve_sources_under)
        self.gavel = gavel or CallbackGavel(lambda **_: False)
        self.resonance = ResonanceEngine(
            policy_store=self.policy,
            philosopher=self.philosopher,
            sandbox=self.sandbox,
            gavel=self.gavel,
            analyzer=self.analyzer,
            bus=self.bus,
            asset_store=self.assets,
            control_questions=["What is Aletheia?", "What does the Philosopher enforce?"],
        )

    # --- corpus ------------------------------------------------------------ #
    def ingest(self, documents: list[Document]) -> int:
        """Index documents for vector search *and* build the knowledge graph."""
        self.vectors.add_documents(documents)
        self.archivist.build_graph(documents)
        return len(documents)

    def ingest_own_docs(self) -> int:
        """Ingest Aletheia's own Markdown design docs (the default use case)."""
        return self.ingest(load_markdown_corpus(_REPO_ROOT))

    # --- the cascade ------------------------------------------------------- #
    async def ask(self, question: str) -> QAResult:
        return await self.nexus.ask(question)

    async def create(self, request: str) -> CreativeResult:
        """Run a creative cascade: Archivist → Narrator → Visionary → Philosopher."""
        return await self.nexus.create(request)

    # --- the Resonance Cycle (supervised self-improvement) ----------------- #
    async def submit_feedback(
        self, *, turn_id: str, question: str, rating: str, note: str = ""
    ) -> ResonanceOutcome:
        """Feed a user verdict on a past turn into the Resonance Cycle.

        Gathers that turn's telemetry (answer, retrieved context, choreography,
        ethical verdict) and runs the four-phase cycle: dissonance → root cause →
        verified proposal → Human Gavel. The post-deploy evaluator re-probes the
        Archivist so the engine can auto-roll-back if the change didn't help.
        """
        feedback = Feedback(turn_id=turn_id, rating=rating, note=note)
        answer = self._asset_for_turn(turn_id, AnswerAsset)
        context = self._asset_for_turn(turn_id, RetrievedContextAsset)
        ethical = self._asset_for_turn(turn_id, SdrEthicalAnalysisReport)
        cascade = self.diagnostician.cascades.get(turn_id)
        choreography = (
            self.diagnostician.build_choreography(cascade) if cascade is not None else None
        )
        offending = self.analyzer.offending_source(answer, context)

        def post_deploy_evaluator():
            # After applying the fix, re-probe: if the offending source no longer
            # grounds the failing answer, treat fidelity as restored.
            still_present = offending in self.archivist.retrieve_sources_under(
                self.policy.current, question
            )
            return self.analyzer.compute_indices(
                choreography=choreography,
                ethical_report=ethical,
                answer=answer,
                feedback=Feedback(turn_id, "INCORRECT" if still_present else "CORRECT"),
            )

        return await self.resonance.run_cycle(
            feedback=feedback,
            failing_question=question,
            answer=answer,
            context=context,
            choreography=choreography,
            ethical_report=ethical,
            post_deploy_evaluator=post_deploy_evaluator,
        )

    def _asset_for_turn(self, turn_id: str, kind: type):
        """Find the most recent asset of ``kind`` belonging to ``turn_id``."""
        match = None
        for asset in self.assets._assets.values():  # type: ignore[attr-defined]
            if isinstance(asset, kind) and getattr(asset, "turn_id", None) == turn_id:
                match = asset
        return match
