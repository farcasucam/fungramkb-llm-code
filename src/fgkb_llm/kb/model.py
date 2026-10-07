"""In-memory data model for a FunGramKB export.

The model is deliberately close to the thesis description (Arcas Túnez, 2008, ch. 3):

* Ontology: three levels of conceptual units, marked by their prefix
  ``#`` metaconcept, ``+`` basic concept, ``$`` terminal concept.
* Every concept has one or more superordinates (multiple inheritance is allowed),
  a semantic type (entity / event / quality), an optional meaning postulate (MP)
  written in COREL, and, for events, a thematic frame.
* Lexicon: lexical units in each language linked to a concept.
* Cognicon: procedural knowledge as scripts (cognitive macrostructures).
* Onomasticon: named instances of concepts.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

SEMANTIC_TYPES = ("entity", "event", "quality")


def concept_level(concept_id: str) -> str:
    """Return the ontological level from the identifier prefix."""
    if concept_id.startswith("#"):
        return "meta"
    if concept_id.startswith("+"):
        return "basic"
    if concept_id.startswith("$"):
        return "terminal"
    raise ValueError(f"Not a FunGramKB concept identifier: {concept_id!r}")


@dataclass
class Concept:
    id: str
    parents: list[str]
    semantic_type: str  # entity | event | quality
    meaning_postulate: str | None = None  # raw COREL text
    thematic_frame: str | None = None  # raw COREL text (events only)
    glosses: dict[str, str] = field(default_factory=dict)  # lang -> gloss
    meta: dict = field(default_factory=dict)  # provenance, domain, frame_source...

    @property
    def level(self) -> str:
        return concept_level(self.id)

    @property
    def is_primitive(self) -> bool:
        """Basic concept whose superordinate is a metaconcept (thesis, 3.1.7.1.1)."""
        return self.level == "basic" and all(p.startswith("#") for p in self.parents)


@dataclass
class LexicalUnit:
    lemma: str
    lang: str  # ISO 639-1, e.g. "en", "es"
    pos: str  # "n", "v", "adj", ...
    concept: str
    corrupt: bool = False  # lemma damaged in the export (lost accents): excluded from linking


@dataclass
class ScriptStep:
    order: int
    predication: str  # raw COREL predication for this step
    label: dict[str, str] = field(default_factory=dict)  # lang -> short NL label for templates
    event: str | None = None
    evar: str | None = None


@dataclass
class Script:
    """Cognicon macrostructure, e.g. 'eating in a restaurant'."""

    id: str
    name: dict[str, str]
    participants: list[str]
    steps: list[ScriptStep]
    preconditions: list[str] = field(default_factory=list)
    relations: list[list[str]] = field(default_factory=list)  # [evarA, evarB, "Before|During|Equals..."]
    description: str = ""


@dataclass
class Instance:
    """Onomasticon entry."""

    id: str
    concept: str
    names: dict[str, str]


@dataclass
class KnowledgeBase:
    concepts: dict[str, Concept] = field(default_factory=dict)
    lexicon: list[LexicalUnit] = field(default_factory=list)
    scripts: dict[str, Script] = field(default_factory=dict)
    instances: dict[str, Instance] = field(default_factory=dict)
    version: str = "unknown"

    # ---- ontology navigation -------------------------------------------------
    def __contains__(self, concept_id: str) -> bool:
        return concept_id in self.concepts

    def get(self, concept_id: str) -> Concept:
        return self.concepts[concept_id]

    def children(self, concept_id: str) -> list[str]:
        return [c.id for c in self.concepts.values() if concept_id in c.parents]

    def ancestors(self, concept_id: str) -> list[str]:
        """All superordinates, nearest first (breadth-first, no duplicates)."""
        seen: list[str] = []
        frontier = list(self.concepts[concept_id].parents) if concept_id in self else []
        while frontier:
            nxt: list[str] = []
            for p in frontier:
                if p not in seen:
                    seen.append(p)
                    if p in self.concepts:
                        nxt.extend(self.concepts[p].parents)
            frontier = nxt
        return seen

    def depth_to(self, concept_id: str, ancestor: str) -> int | None:
        """Number of IS-A hops from concept to ancestor, or None."""
        frontier, depth, seen = {concept_id}, 0, set()
        while frontier:
            if ancestor in frontier:
                return depth
            seen |= frontier
            frontier = {
                p for c in frontier if c in self.concepts for p in self.concepts[c].parents
            } - seen
            depth += 1
        return None

    def by_type(self, semantic_type: str) -> list[Concept]:
        return [c for c in self.concepts.values() if c.semantic_type == semantic_type]

    def with_postulates(self) -> Iterator[Concept]:
        return (c for c in self.concepts.values() if c.meaning_postulate)

    # ---- lexicon -----------------------------------------------------------
    def senses(self, lemma: str, lang: str) -> list[str]:
        lemma = lemma.lower()
        return [lu.concept for lu in self.lexicon if lu.lang == lang and lu.lemma.lower() == lemma and not lu.corrupt]

    def lemmas(self, concept_id: str, lang: str) -> list[str]:
        return [lu.lemma for lu in self.lexicon if lu.lang == lang and lu.concept == concept_id and not lu.corrupt]

    def label(self, concept_id: str, lang: str = "en") -> str:
        """Human-readable label: first lemma, else the bare concept name."""
        lem = self.lemmas(concept_id, lang)
        if lem:
            return lem[0]
        bare = concept_id.lstrip("#+$")
        return bare.rsplit("_", 1)[0].replace("_", " ").lower()

    def subset(self, concept_ids: Iterable[str]) -> KnowledgeBase:
        keep = set(concept_ids)
        return KnowledgeBase(
            concepts={k: v for k, v in self.concepts.items() if k in keep},
            lexicon=[lu for lu in self.lexicon if lu.concept in keep],
            scripts=dict(self.scripts),
            instances={k: v for k, v in self.instances.items() if v.concept in keep},
            version=self.version,
        )
