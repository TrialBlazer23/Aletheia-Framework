"""Aletheia's safety layer — the Prime Directives and the rule-based validator.

This is defense-in-depth Layer 1 (the constitution) + the deterministic floor of
Layer 2 (the Philosopher's runtime checks). The Philosopher agent itself lives in
``aletheia/agents/philosopher.py``.
"""

from aletheia.safety.prime_directives import Directive, PrimeDirectives, Rule
from aletheia.safety.validator import RuleBasedValidator, Violation

__all__ = ["PrimeDirectives", "Directive", "Rule", "RuleBasedValidator", "Violation"]
