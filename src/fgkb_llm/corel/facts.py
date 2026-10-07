"""Flatten meaning postulates into reasoning facts.

A *property* is what a predication says about the definiendum, normalised as

    Prop(event, self_role, other_role, filler)

e.g. BIRD  *(e3: +FLY_00 (x1)Agent ...)            -> Prop(+FLY_00, Agent, "", "")
     BIRD  *(e2: +COMPRISE_00 (x1)Theme (x3: m +FEATHER_00 & ...)Referent)
                                                    -> Prop(+COMPRISE_00, Theme, Referent, +FEATHER_00), ...
     OSTRICH +(e9: n +FLY_00 (x1)Agent ...)          -> negative Prop(+FLY_00, Agent, "", "")

The first-level ``BE_00 (x1: C)Theme (x2: D)Referent`` predication is read as a
classificatory (IS-A) statement, not as a property.

Subset limitations (documented, see docs/PROMPTS.md P03):
* only participants co-indexed with the definiendum produce properties;
* predications used as fillers of satellites (Reason, Condition, Scene...) are kept
  as `complex` facts for verbalisation but are not used by the reasoner;
* disjunctive / exclusive selection preferences become a single property whose
  filler is the disjunction string (no case splitting).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .ast import MeaningPostulate, Predication, SelGroup, SelVar
from .parser import parse

CLASSIFY_EVENTS = {"+BE_00", "BE_00"}


@dataclass(frozen=True)
class Prop:
    event: str
    self_role: str
    other_role: str = ""
    filler: str = ""
    quant: str = field(default="", compare=False)
    subj_role: str = field(default="", compare=False)  # highest-ranked role in the predication

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.event, self.self_role, self.other_role, self.filler)


@dataclass(frozen=True)
class Fact:
    concept: str
    prop: Prop
    strict: bool
    negated: bool
    source: str  # "<concept>/<evar>" for traceability


@dataclass(frozen=True)
class IsA:
    child: str
    parent: str
    strict: bool
    source: str


def _definiendum_vars(mp: MeaningPostulate, concept: str) -> set[str]:
    """Variables bound to the definiendum (explicitly or as x1 by convention)."""
    bound = {"x1"}
    for _, pred in mp.predications():
        for part in pred.participants:
            if concept in part.filler_concepts() and not part.is_satellite:
                bound.add(part.var)
    return bound


def _coref(mp: MeaningPostulate) -> dict:
    """Variable -> first participant that carries its selection preferences.

    COREL states a participant's preferences once ("(x3: +ALCOHOL_00)Referent") and later
    predications refer to it by variable only ("(x3)Theme"); those must share the filler."""
    out: dict = {}
    for _, pred in mp.predications():
        for part in pred.participants:
            if part.filler is not None and not isinstance(part.filler, (list, SelVar)):
                out.setdefault(part.var, part)
    return out


def _fillers(part, coref: dict | None = None) -> list[tuple[str, str]]:
    """(filler, quant) pairs for a participant with selection preferences."""
    f = part.filler
    if f is None and coref and part.var in coref:
        f = coref[part.var].filler
    if f is None or isinstance(f, (list, SelVar)):
        return []
    if isinstance(f, SelGroup) and not f.is_conjunctive:
        return [(str(f), "")]
    if isinstance(f, SelGroup):
        out = []
        for it in f.items:
            if isinstance(it, SelGroup):
                out.append((str(it), ""))
            elif isinstance(it, SelVar):
                continue
            elif it.negated:
                continue  # negated preference: not a positive filler
            else:
                out.append((it.concept, it.quant or ""))
        return out
    if getattr(f, "negated", False):
        return []
    return [(f.concept, f.quant or "")]


def extract(concept: str, mp: MeaningPostulate) -> tuple[list[IsA], list[Fact]]:
    selfvars = _definiendum_vars(mp, concept)
    coref = _coref(mp)
    isas: list[IsA] = []
    facts: list[Fact] = []
    for item in mp.items:
        for idx, pred in enumerate(item.predications):
            # inside a linked group only the first predication speaks about the definiendum
            if item.linked and idx > 0:
                continue
            src = f"{concept}/{pred.evar}"
            selfparts = [p for p in pred.participants if p.var in selfvars]
            if not selfparts:
                continue
            if pred.event in CLASSIFY_EVENTS and not pred.negated:
                for p in pred.participants:
                    if p.role == "Referent" and p.var not in selfvars:
                        for fill, _ in _fillers(p):
                            # "x is a D or an E" (| ^) is not an IS-A link to either; conjunctions are split
                            if not any(op in fill for op in ("|", "^")):
                                isas.append(IsA(concept, fill, item.strict, src))
                continue
            self_role = selfparts[0].role
            present = {p.role for p in pred.participants}
            subj = next((r for r in ("Agent", "Theme", "Referent", "Attribute") if r in present), self_role)
            others = [p for p in pred.participants if p.var not in selfvars]
            produced = False
            for p in others:
                for fill, quant in _fillers(p, coref):
                    facts.append(
                        Fact(concept, Prop(pred.event, self_role, p.role, fill, quant, subj),
                             item.strict, pred.negated, src)
                    )
                    produced = True
            if not produced:
                facts.append(Fact(concept, Prop(pred.event, self_role, subj_role=subj), item.strict, pred.negated, src))
    return isas, facts


def extract_kb(kb) -> tuple[list[IsA], list[Fact], dict[str, str]]:
    """Run extraction over every concept with a postulate. Returns (isas, facts, errors)."""
    isas: list[IsA] = []
    facts: list[Fact] = []
    errors: dict[str, str] = {}
    for c in kb.with_postulates():
        if c.semantic_type != "entity":
            # In event and quality postulates x1 is a participant (the doer, the bearer of the
            # quality), not the definiendum: they define the predicate, not properties of x1.
            continue
        try:
            mp = parse(c.meaning_postulate)
        except ValueError as exc:
            errors[c.id] = str(exc).splitlines()[0]
            continue
        i, f = extract(c.id, mp)
        isas.extend(i)
        facts.extend(f)
    return isas, facts, errors


def predication_to_prop(pred: Predication, subject_var: str = "x1") -> tuple[Prop | None, bool]:
    """Map a *query* predication (from the neuro-symbolic pipeline) to a Prop.

    Returns (prop, negated). The subject is the participant bound to ``subject_var``.
    """
    subj = [p for p in pred.participants if p.var == subject_var]
    if not subj:
        return None, pred.negated
    others = [p for p in pred.participants if p.var != subject_var and p.filler is not None]
    if others:
        fills = _fillers(others[0])
        if fills:
            return Prop(pred.event, subj[0].role, others[0].role, fills[0][0]), pred.negated
    return Prop(pred.event, subj[0].role), pred.negated
