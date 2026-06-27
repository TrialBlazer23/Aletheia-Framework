"""Load the Prime Directives constitution from ``prime_directives.yaml``.

Provides typed access to the four directives and the rule set the Philosopher
enforces. The YAML ships next to this module and is loaded by default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

_DEFAULT_PATH = Path(__file__).resolve().parent / "prime_directives.yaml"

# Severities, ordered least → most severe.
SEVERITY_ORDER = {"MEDIUM": 0, "HIGH": 1, "CRITICAL": 2}


@dataclass(frozen=True)
class Directive:
    id: str
    name: str
    rank: int
    statement: str


@dataclass(frozen=True)
class Rule:
    name: str
    description: str
    directive: str  # directive id (e.g. "PD4")
    severity: str  # MEDIUM | HIGH | CRITICAL
    type: str  # "regex" | "keyword"
    pattern: str | None = None
    keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PrimeDirectives:
    version: str
    directives: list[Directive]
    rules: list[Rule]

    def directive(self, directive_id: str) -> Directive | None:
        return next((d for d in self.directives if d.id == directive_id), None)

    @classmethod
    def load(cls, path: str | Path | None = None) -> "PrimeDirectives":
        data = yaml.safe_load(Path(path or _DEFAULT_PATH).read_text(encoding="utf-8"))
        directives = [
            Directive(id=d["id"], name=d["name"], rank=d["rank"], statement=d["statement"].strip())
            for d in data.get("directives", [])
        ]
        rules = [
            Rule(
                name=r["name"],
                description=r.get("description", ""),
                directive=r["directive"],
                severity=r["severity"],
                type=r["type"],
                pattern=r.get("pattern"),
                keywords=list(r.get("keywords", [])),
            )
            for r in data.get("rules", [])
        ]
        return cls(version=str(data.get("version", "1.0")), directives=directives, rules=rules)
