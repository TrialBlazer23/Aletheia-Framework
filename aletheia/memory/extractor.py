"""Knowledge extraction — the Archivist's deterministic, neuro-symbolic core.

CLAUDE.md §2 / ROADMAP design-decision #4: the Archivist builds its knowledge
graph by **deterministic (spaCy) parsing**. That is the anti-hallucination
thesis and it is non-negotiable — facts come from grammar, not from a model's
imagination. This module turns text into ``(entities, facts)`` by walking the
spaCy dependency tree for subject–predicate–object relations (including copulas
and participial modifiers like "the Philosopher *enforcing* the Prime
Directives").

Behind a small interface, as ever, so the Archivist never imports spaCy
directly. If no spaCy model is installed, we degrade — exactly like the LLM
provider does — to a dependency-free ``RuleBasedExtractor`` so the system still
runs and still builds a (smaller) graph. The deterministic spaCy parse is the
design's intent and the default; the rule-based layer is only a floor.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

# spaCy models, in the design's order of preference. en_core_web_lg is what the
# design names; we fall back to the smaller models (identical dependency parser,
# lighter footprint) so the graph builds in any environment.
_SPACY_MODELS = ("en_core_web_lg", "en_core_web_md", "en_core_web_sm")

_SUBJECT_DEPS = {"nsubj", "nsubjpass", "nsubj:pass", "csubj"}
_OBJECT_DEPS = {"dobj", "obj", "dative", "attr", "oprd", "acomp"}
_PARTICIPLE_DEPS = {"acl", "advcl", "relcl"}

# Markdown/code artifacts that mark a noun phrase as junk rather than prose.
_JUNK_CHARS = set("*|`→#[]{}<>\\")
_MAX_NP_TOKENS = 6


def _is_clean(np: str) -> bool:
    """Reject noun phrases that are markdown/code noise rather than real prose.

    The corpus is raw Markdown — tables, code fences, and ``**bold**`` runs parse
    into garbage triples. A clean entity has alphabetic content, no markup
    characters, no newlines, and a sane length.
    """
    if not np or "\n" in np:
        return False
    if any(ch in _JUNK_CHARS for ch in np):
        return False
    if not any(ch.isalpha() for ch in np):
        return False
    return len(np.split()) <= _MAX_NP_TOKENS


@dataclass(frozen=True)
class ExtractedEntity:
    name: str
    label: str  # e.g. PERSON, ORG, CONCEPT


@dataclass(frozen=True)
class ExtractedFact:
    subject: str
    predicate: str  # the verb lemma (+ particle/preposition)
    object: str
    sentence: str  # the source sentence — the evidence behind the fact


class KnowledgeExtractor(ABC):
    name: str = "extractor"
    is_deterministic: bool = True

    @abstractmethod
    def extract(self, text: str) -> tuple[list[ExtractedEntity], list[ExtractedFact]]:
        ...


# --------------------------------------------------------------------------- #
# The real thing: spaCy dependency parsing
# --------------------------------------------------------------------------- #
class SpacyExtractor(KnowledgeExtractor):
    is_deterministic = True

    def __init__(self, model: str | None = None) -> None:
        import spacy

        last_err: Exception | None = None
        candidates = (model,) if model else _SPACY_MODELS
        for candidate in candidates:
            if candidate is None:
                continue
            try:
                # Keep the lemmatizer (predicates are verb lemmas) but drop NER
                # only if missing; the parser + tagger + lemmatizer are required.
                self._nlp = spacy.load(candidate)
                self.name = f"spaCy ({candidate})"
                self._model = candidate
                break
            except Exception as exc:  # noqa: BLE001 — try the next model
                last_err = exc
        else:
            raise RuntimeError(
                f"no spaCy model available (tried {candidates}): {last_err!r}"
            )

    def extract(self, text: str) -> tuple[list[ExtractedEntity], list[ExtractedFact]]:
        doc = self._nlp(text)
        entities: dict[str, ExtractedEntity] = {}
        facts: list[ExtractedFact] = []

        for ent in doc.ents:
            name = ent.text.strip()
            if name:
                entities.setdefault(name.lower(), ExtractedEntity(name=name, label=ent.label_))
        for chunk in doc.noun_chunks:
            # Keep noun chunks tight: long or verb-bearing spans (common when
            # markdown runs sentences together) make noisy, useless entities.
            if len(chunk) > 5 or any(t.pos_ in {"VERB", "AUX"} for t in chunk):
                continue
            name = self._clean_span(chunk)
            if name and name.lower() not in entities:
                entities.setdefault(name.lower(), ExtractedEntity(name=name, label="CONCEPT"))

        for sent in doc.sents:
            facts.extend(self._facts_in_sentence(sent))
        return list(entities.values()), facts

    def _facts_in_sentence(self, sent) -> list[ExtractedFact]:
        out: list[ExtractedFact] = []
        sentence = sent.text.strip()
        for tok in sent:
            if tok.pos_ not in {"VERB", "AUX"}:
                continue
            # Skip bare-pronoun subjects ("it", "that", "they") — without their
            # referent they make uninformative facts.
            subjects = [
                c for c in tok.children if c.dep_ in _SUBJECT_DEPS and c.pos_ != "PRON"
            ]
            # Participial / relative modifier: "the Philosopher enforcing X" —
            # the verb's head noun is the implicit subject. In that case the verb
            # sits *inside* the subject noun's subtree, so we must subtract the
            # verb's subtree when reading the subject phrase off the tree.
            participle = False
            if not subjects and tok.dep_ in _PARTICIPLE_DEPS and tok.head.pos_ in {"NOUN", "PROPN"}:
                subjects = [tok.head]
                participle = True
            if not subjects:
                continue

            base_pred = tok.lemma_ if tok.lemma_ != "-PRON-" else tok.text
            # Each object carries its own predicate: a direct object keeps the
            # bare verb ("monitor the bus"); a prepositional object folds the
            # preposition in ("monitor for failures").
            obj_preds: list[tuple] = [
                (c, base_pred) for c in tok.children if c.dep_ in _OBJECT_DEPS
            ]
            for child in tok.children:
                if child.dep_ == "prep":
                    for pobj in (g for g in child.children if g.dep_ == "pobj"):
                        obj_preds.append((pobj, f"{base_pred} {child.text}"))

            for subj in subjects:
                subj_np = self._np(subj, exclude=tok if participle else None)
                if not _is_clean(subj_np):
                    continue
                for obj, predicate in obj_preds:
                    obj_np = self._np(obj)
                    if _is_clean(obj_np) and subj_np.lower() != obj_np.lower():
                        out.append(
                            ExtractedFact(
                                subject=subj_np,
                                predicate=predicate.strip().lower(),
                                object=obj_np,
                                sentence=sentence,
                            )
                        )
        return out

    def _np(self, token, *, exclude=None) -> str:
        """The noun phrase under ``token``, optionally minus a sub-clause subtree.

        ``exclude`` drops a participle verb's own subtree so the subject of "the
        Philosopher enforcing X" is just "the Philosopher", not the whole span.
        """
        excluded = set(exclude.subtree) if exclude is not None else set()
        toks = sorted(
            (t for t in token.subtree if t not in excluded), key=lambda t: t.i
        )
        while toks and toks[0].pos_ in {"DET", "PUNCT"}:
            toks = toks[1:]
        while toks and toks[-1].pos_ == "PUNCT":
            toks = toks[:-1]
        return " ".join(t.text for t in toks).strip()

    @staticmethod
    def _clean_span(span) -> str:
        toks = [t for t in span if t.pos_ != "DET"]
        return " ".join(t.text for t in toks).strip()


# --------------------------------------------------------------------------- #
# The floor: a dependency-free rule-based extractor
# --------------------------------------------------------------------------- #
class RuleBasedExtractor(KnowledgeExtractor):
    """A tiny "<Subject> <verb> <Object>" matcher for when spaCy is absent.

    Deliberately simple: it catches a handful of common relational verbs in
    well-formed sentences so the graph is never empty. It is a fallback, not a
    parser — the spaCy path is the design's real extractor.
    """

    is_deterministic = True
    name = "rule-based (no spaCy)"

    _VERBS = (
        "enforces", "enforce", "enforcing", "validates", "validate",
        "monitors", "monitor", "builds", "build", "orchestrates", "orchestrate",
        "decomposes", "synthesizes", "synthesize", "is", "are", "ingests",
        "generates", "generate", "detects", "detect", "produces", "produce",
    )
    _SENT_RE = re.compile(r"[^.!?\n]+[.!?]")

    def __init__(self) -> None:
        verbs = "|".join(sorted(self._VERBS, key=len, reverse=True))
        self._triple_re = re.compile(
            rf"\b(?P<subj>[A-Z][\w-]+(?:\s+[\w-]+){{0,3}}?)\s+"
            rf"(?P<verb>{verbs})\s+"
            rf"(?P<obj>(?:the\s+|a\s+|an\s+)?[\w-]+(?:\s+[\w-]+){{0,4}})",
        )

    def extract(self, text: str) -> tuple[list[ExtractedEntity], list[ExtractedFact]]:
        entities: dict[str, ExtractedEntity] = {}
        facts: list[ExtractedFact] = []
        for m in self._SENT_RE.finditer(text):
            sentence = m.group(0).strip()
            tm = self._triple_re.search(sentence)
            if not tm:
                continue
            subj = tm.group("subj").strip()
            obj = self._strip_det(tm.group("obj").strip())
            verb = tm.group("verb").lower()
            predicate = "be" if verb in {"is", "are"} else verb.rstrip("s").replace("ing", "")
            if subj and obj and subj.lower() != obj.lower():
                facts.append(
                    ExtractedFact(subject=subj, predicate=predicate, object=obj, sentence=sentence)
                )
                for name in (subj, obj):
                    entities.setdefault(name.lower(), ExtractedEntity(name=name, label="CONCEPT"))
        return list(entities.values()), facts

    @staticmethod
    def _strip_det(text: str) -> str:
        return re.sub(r"^(the|a|an)\s+", "", text, flags=re.IGNORECASE).strip()


_CACHED_EXTRACTOR: KnowledgeExtractor | None = None


def get_default_extractor() -> KnowledgeExtractor:
    """Prefer the deterministic spaCy parser; fall back to rules if it's absent.

    Cached process-wide: loading a spaCy model costs ~0.5s, so we do it once and
    reuse it across every ``QASystem`` (and every test).
    """
    global _CACHED_EXTRACTOR
    if _CACHED_EXTRACTOR is not None:
        return _CACHED_EXTRACTOR
    try:
        _CACHED_EXTRACTOR = SpacyExtractor()
    except Exception as exc:  # noqa: BLE001 — spaCy or its model isn't installed
        print(
            f"[aletheia] spaCy unavailable ({type(exc).__name__}); "
            "Archivist using the rule-based extractor (install en_core_web_sm "
            "for the full knowledge graph)."
        )
        _CACHED_EXTRACTOR = RuleBasedExtractor()
    return _CACHED_EXTRACTOR
