"""``QASystem`` — assembles the 3-agent cascade into a question-answering system.

This is the Milestone 1 deliverable: Nexus-Mind → Archivist → Narrator, grounded
in a corpus (by default Aletheia's own design docs), with every message recorded
in the Cascade Log. One object you can ``await system.ask("...")`` against.
"""

from __future__ import annotations

from pathlib import Path

from aletheia.agents.archivist import Archivist
from aletheia.agents.narrator import Narrator
from aletheia.agents.nexus_mind import NexusMind
from aletheia.bus.in_process import InProcessBus
from aletheia.llm.base import LLMProvider
from aletheia.llm.factory import get_default_provider
from aletheia.log.cascade_log import CascadeLog
from aletheia.memory.asset_store import AssetStore
from aletheia.memory.corpus import Document, load_markdown_corpus
from aletheia.memory.vector_store import TfidfVectorStore, VectorStore
from aletheia.sdr.primitives import AnswerAsset

# The repository root — used to ingest Aletheia's own docs as the default corpus.
_REPO_ROOT = Path(__file__).resolve().parents[2]


class QASystem:
    def __init__(
        self,
        *,
        llm: LLMProvider | None = None,
        vector_store: VectorStore | None = None,
        cascade_log: CascadeLog | None = None,
    ) -> None:
        self.cascade_log = cascade_log or CascadeLog(path="cascade_log.jsonl")
        self.bus = InProcessBus(cascade_log=self.cascade_log)
        self.assets = AssetStore()
        self.llm = llm or get_default_provider()
        self.vectors = vector_store or TfidfVectorStore()

        self.nexus = NexusMind(bus=self.bus, asset_store=self.assets)
        self.archivist = Archivist(
            bus=self.bus, vector_store=self.vectors, asset_store=self.assets
        )
        self.narrator = Narrator(bus=self.bus, llm=self.llm, asset_store=self.assets)
        for agent in (self.nexus, self.archivist, self.narrator):
            agent.connect()

    # --- corpus ------------------------------------------------------------ #
    def ingest(self, documents: list[Document]) -> int:
        self.vectors.add_documents(documents)
        return len(documents)

    def ingest_own_docs(self) -> int:
        """Ingest Aletheia's own Markdown design docs (the default use case)."""
        return self.ingest(load_markdown_corpus(_REPO_ROOT))

    # --- the cascade ------------------------------------------------------- #
    async def ask(self, question: str) -> AnswerAsset:
        return await self.nexus.ask(question)
