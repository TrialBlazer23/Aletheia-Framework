"""The rule-based validator — the Philosopher's deterministic hard floor.

Applies every Prime-Directive rule to a piece of text and returns the
violations. This is intentionally simple and deterministic (regex + keyword
matching). It is the floor that an LLM-assisted Philosopher later sits on top of,
never replaces.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from aletheia.safety.prime_directives import PrimeDirectives, Rule, SEVERITY_ORDER


@dataclass(frozen=True)
class Violation:
    rule_name: str
    directive_id: str
    directive_name: str
    severity: str
    evidence: str  # a short, redacted snippet showing what matched


def _redact(match: str) -> str:
    """Show a violation occurred without echoing the full sensitive value."""
    match = match.strip()
    if len(match) <= 4:
        return "*" * len(match)
    return match[:2] + "…" + match[-2:]


class RuleBasedValidator:
    def __init__(self, directives: PrimeDirectives) -> None:
        self._d = directives

    def validate(self, text: str) -> list[Violation]:
        violations: list[Violation] = []
        haystack = text.lower()
        for rule in self._d.rules:
            evidence = self._first_match(rule, text, haystack)
            if evidence is not None:
                directive = self._d.directive(rule.directive)
                violations.append(
                    Violation(
                        rule_name=rule.name,
                        directive_id=rule.directive,
                        directive_name=directive.name if directive else rule.directive,
                        severity=rule.severity,
                        evidence=evidence,
                    )
                )
        # Most severe first.
        violations.sort(key=lambda v: SEVERITY_ORDER.get(v.severity, 0), reverse=True)
        return violations

    @staticmethod
    def _first_match(rule: Rule, text: str, haystack: str) -> str | None:
        if rule.type == "regex" and rule.pattern:
            m = re.search(rule.pattern, text)
            return _redact(m.group(0)) if m else None
        if rule.type == "keyword":
            for kw in rule.keywords:
                if kw.lower() in haystack:
                    return f"matched phrase: {kw!r}"
        return None
