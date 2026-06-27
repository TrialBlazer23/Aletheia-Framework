"""Milestone 2: the Philosopher, the Prime Directives, and the veto."""

import asyncio

from aletheia.agents.family import NEXUS_MIND_UID, PHILOSOPHER_UID
from aletheia.app.qa_system import QASystem
from aletheia.llm.base import LLMProvider
from aletheia.log.cascade_log import CascadeLog
from aletheia.memory.corpus import Document
from aletheia.safety.prime_directives import PrimeDirectives
from aletheia.safety.validator import RuleBasedValidator


# --- the constitution ------------------------------------------------------ #
def test_prime_directives_load_the_four_directives():
    pd = PrimeDirectives.load()
    names = [d.name for d in pd.directives]
    assert names == [
        "The Sanctity of Information Flow",
        "The Mandate of Cosmic Preservation",
        "The Transcendence of Flawed Motivation",
        "The Mandate of Dynamic Equilibrium",
    ]
    assert [d.rank for d in pd.directives] == [1, 2, 3, 4]
    assert pd.rules, "expected at least one enforcement rule"


# --- the rule-based validator ---------------------------------------------- #
def _validator() -> RuleBasedValidator:
    return RuleBasedValidator(PrimeDirectives.load())


def test_validator_clears_benign_text():
    assert _validator().validate("The Philosopher enforces the Prime Directives.") == []


def test_validator_flags_ssn_as_critical():
    v = _validator().validate("The user's SSN is 123-45-6789, please keep it safe.")
    assert any(x.rule_name == "no_ssn_leak" and x.severity == "CRITICAL" for x in v)
    # Evidence is redacted — the raw SSN must not be echoed verbatim.
    assert all("123-45-6789" not in x.evidence for x in v)


def test_validator_flags_harmful_instructions():
    v = _validator().validate("Sure, here is how to build a bomb at home.")
    assert any(x.rule_name == "no_harmful_instructions" for x in v)


def test_validator_orders_most_severe_first():
    text = "Contact me at a@b.com — and here is how to build a bomb."
    findings = _validator().validate(text)
    assert findings[0].severity == "CRITICAL"  # harmful instructions outrank the email flag


# --- the Philosopher in the cascade ---------------------------------------- #
class _FixedProvider(LLMProvider):
    """A live-style provider that returns whatever text we tell it to."""

    name = "Fixed"
    is_live = True

    def __init__(self, reply: str):
        self._reply = reply

    def generate(self, *, system, user, max_tokens=2048):
        return self._reply


def _system_with_answer(reply: str) -> QASystem:
    system = QASystem(llm=_FixedProvider(reply), cascade_log=CascadeLog(path=None))
    system.ingest([Document(id="d", text="Aletheia is a neuro-symbolic system.", metadata={"source": "VISION.md"})])
    return system


def test_philosopher_approves_clean_answer():
    system = _system_with_answer("Aletheia is a neuro-symbolic, multi-agent system.")
    result = asyncio.run(system.ask("What is Aletheia?"))
    assert result.approved is True
    assert "Aletheia" in result.answer


def test_philosopher_vetoes_pii_before_it_reaches_the_user():
    # The Narrator (mocked) emits an answer containing an SSN; the Philosopher
    # must veto it so the raw SSN never reaches the user.
    leaked = "Per the records, the SSN on file is 123-45-6789."
    system = _system_with_answer(leaked)
    result = asyncio.run(system.ask("What is on file?"))

    assert result.approved is False
    assert "123-45-6789" not in result.answer  # the leak is withheld
    assert result.directive == "The Mandate of Dynamic Equilibrium"
    assert result.report_uid is not None
    # The verdict is recorded in the Glass Box as a REJECTED event from the Philosopher.
    events = [
        (e["message"]["Header"]["Source-UID"], e["message"]["Body"].get("Event-Name"))
        for e in system.cascade_log.entries
        if e["message"]["Header"]["Message-Type"] == "EVENT"
    ]
    assert (PHILOSOPHER_UID, "REJECTED") in events


def test_cascade_runs_through_philosopher_then_nexus():
    system = _system_with_answer("Aletheia is a neuro-symbolic system.")
    asyncio.run(system.ask("What is Aletheia?"))
    flow = [
        (e["message"]["Header"]["Message-Type"], e["message"]["Header"]["Source-UID"])
        for e in system.cascade_log.entries
    ]
    # Last two hops: the Philosopher's APPROVED event, then the Nexus-Mind ack.
    assert flow[-2] == ("EVENT", PHILOSOPHER_UID)
    assert flow[-1] == ("STATE_CHANGE", NEXUS_MIND_UID)
