"""Corpus loading — ingest Aletheia's own design docs for the first use case.

Walks a directory for Markdown files and splits each into reasonably-sized
chunks anchored to their nearest heading, so retrieved passages carry a
meaningful source label (file + section) for attribution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Folders we never ingest.
_SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".snapshots", ".github", ".codacy"}
_MAX_CHARS = 1200  # soft cap per chunk
_MIN_CHARS = 80  # drop trivially small chunks


@dataclass
class Document:
    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _chunk_markdown(path: Path, root: Path) -> list[Document]:
    rel = path.relative_to(root).as_posix()
    heading = path.stem
    buf: list[str] = []
    chunks: list[Document] = []
    counter = 0

    def flush() -> None:
        nonlocal counter, buf
        body = "\n".join(buf).strip()
        buf = []
        if len(body) < _MIN_CHARS:
            return
        counter += 1
        source = f"{rel} › {heading}" if heading else rel
        chunks.append(
            Document(
                id=f"{rel}#{counter}",
                text=body,
                metadata={"source": source, "path": rel, "heading": heading},
            )
        )

    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("#"):
            flush()
            heading = line.lstrip("#").strip() or heading
            continue
        buf.append(line)
        if sum(len(b) for b in buf) >= _MAX_CHARS and line.strip() == "":
            flush()
    flush()
    return chunks


def load_markdown_corpus(root: str | Path) -> list[Document]:
    """Load and chunk every Markdown file under ``root`` (recursively)."""
    root = Path(root)
    docs: list[Document] = []
    for path in sorted(root.rglob("*.md")):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        docs.extend(_chunk_markdown(path, root))
    return docs
