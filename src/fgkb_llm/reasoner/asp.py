"""Answer-set-programming reasoner over FunGramKB meaning postulates.

Implements the inheritance behaviour described in the thesis (ch. 5, MicroKnowing):
strict predications (+) are inherited without exception; defeasible predications (*)
are inherited unless a more specific concept states the opposite (e.g. BIRD flies,
OSTRICH does not). Multiple inheritance is allowed; unresolved clashes between
unrelated ancestors are reported as ``conflict``.

Each answer carries a *trace*: the ancestor whose postulate supports it, the
predication id and whether it was strict, so answers are verifiable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import clingo

from ..corel.facts import Fact, IsA, Prop, extract_kb
from ..kb.model import KnowledgeBase

RULES = r"""
anc(X,X) :- concept(X).
anc(X,Z) :- isa(X,Y), anc(Y,Z).

pos(C,P) :- sprop(C,P).   pos(C,P) :- dprop(C,P).
neg(C,P) :- sneg(C,P).    neg(C,P) :- dneg(C,P).

sholds(X,P)  :- anc(X,Y), sprop(Y,P).
snholds(X,P) :- anc(X,Y), sneg(Y,P).

blockp(X,P,Y) :- anc(X,Y), dprop(Y,P), anc(X,Z), neg(Z,P), anc(Z,Y), Z != Y.
blockn(X,P,Y) :- anc(X,Y), dneg(Y,P), anc(X,Z), pos(Z,P), anc(Z,Y), Z != Y.

supp(X,P,Y,strict)     :- anc(X,Y), sprop(Y,P).
supp(X,P,Y,default)    :- anc(X,Y), dprop(Y,P), not blockp(X,P,Y), not snholds(X,P).
nsupp(X,P,Y,strict)    :- anc(X,Y), sneg(Y,P).
nsupp(X,P,Y,default)   :- anc(X,Y), dneg(Y,P), not blockn(X,P,Y), not sholds(X,P).

holds(X,P)  :- supp(X,P,_,_),  focus(X).
nholds(X,P) :- nsupp(X,P,_,_), focus(X).

#show holds/2. #show nholds/2. #show supp/4. #show nsupp/4.
"""


def _q(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


@dataclass
class Answer:
    status: str  # "true" | "false" | "unknown" | "conflict"
    support: list[tuple[str, str, str]] = field(default_factory=list)  # (ancestor, strict|default, source)

    @property
    def strict(self) -> bool:
        return any(s[1] == "strict" for s in self.support)


class Reasoner:
    def __init__(self, kb: KnowledgeBase, mp_isa: bool = True):
        """``mp_isa``: also read BE_00 classification predications as IS-A links.
        Disabled for the corrupted-KB control so its taxonomy stays identical."""
        self.kb = kb
        mp_isas, facts, self.parse_errors = extract_kb(kb)
        self.parents: dict[str, set[str]] = {cid: set(c.parents) for cid, c in kb.concepts.items()}
        if mp_isa:
            for i in mp_isas:
                self.parents.setdefault(i.child, set()).add(i.parent)
        self.mp_isas: list[IsA] = mp_isas
        self.facts: list[Fact] = facts
        self.facts_by_concept: dict[str, list[Fact]] = {}
        for f in facts:
            self.facts_by_concept.setdefault(f.concept, []).append(f)
        self._prop_ids: dict[tuple, str] = {}
        self._props: dict[str, Prop] = {}
        for f in facts:
            self._pid(f.prop)

    def patched(self, kb2: KnowledgeBase, changed: list[str]) -> Reasoner:
        """Cheap copy for a KB that differs only in the ``changed`` concepts (re-extracts just those)."""
        from ..corel.facts import extract
        from ..corel.parser import parse

        r = object.__new__(Reasoner)
        r.kb = kb2
        r.parse_errors = dict(self.parse_errors)
        r.parents = {k: set(v) for k, v in self.parents.items()}
        r.mp_isas = [i for i in self.mp_isas if i.child not in changed]
        r.facts = [f for f in self.facts if f.concept not in changed]
        for cid in changed:
            c = kb2.concepts[cid]
            r.parents[cid] = set(c.parents)
            if c.meaning_postulate:
                i, f = extract(cid, parse(c.meaning_postulate))
                r.mp_isas += i
                r.facts += f
                for e in i:
                    r.parents[cid].add(e.parent)
        r.facts_by_concept = {}
        for f in r.facts:
            r.facts_by_concept.setdefault(f.concept, []).append(f)
        r._prop_ids = dict(self._prop_ids)
        r._props = dict(self._props)
        for f in r.facts:
            r._pid(f.prop)
        r._closure_cache = {}
        return r

    # ---- helpers -------------------------------------------------------------
    def _pid(self, prop: Prop) -> str:
        key = prop.key
        if key not in self._prop_ids:
            pid = f"p{len(self._prop_ids)}"
            self._prop_ids[key] = pid
            self._props[pid] = prop  # keeps the first-seen quantifier for verbalisation
        return self._prop_ids[key]

    def ancestors_or_self(self, concept: str) -> set[str]:
        seen, stack = set(), [concept]
        while stack:
            c = stack.pop()
            if c in seen:
                continue
            seen.add(c)
            stack.extend(self.parents.get(c, ()))
        return seen

    def depth(self, concept: str, ancestor: str) -> int | None:
        frontier, d, seen = {concept}, 0, set()
        while frontier:
            if ancestor in frontier:
                return d
            seen |= frontier
            frontier = {p for c in frontier for p in self.parents.get(c, ())} - seen
            d += 1
        return None

    def _program(self, focus: set[str], extra: list[Fact] | None = None) -> str:
        scope: set[str] = set()
        for c in focus:
            scope |= self.ancestors_or_self(c)
        lines = [RULES]
        for c in scope:
            lines.append(f"concept({_q(c)}).")
            for p in self.parents.get(c, ()):
                lines.append(f"isa({_q(c)},{_q(p)}).")
        for c in focus:
            lines.append(f"focus({_q(c)}).")
        fact_list = [f for c in scope for f in self.facts_by_concept.get(c, [])] + list(extra or [])
        for f in fact_list:
            pred = ("s" if f.strict else "d") + ("neg" if f.negated else "prop")
            lines.append(f"{pred}({_q(f.concept)},{_q(self._pid(f.prop))}).")
            lines.append(f"% src {f.source}")
        return "\n".join(lines)

    def _solve(self, focus: set[str], extra: list[Fact] | None = None):
        ctl = clingo.Control(["--warn=none"])
        ctl.add("base", [], self._program(focus, extra))
        ctl.ground([("base", [])])
        atoms: list[clingo.Symbol] = []
        ctl.solve(on_model=lambda m: atoms.extend(m.symbols(shown=True)))
        return atoms

    # ---- public API ----------------------------------------------------------
    def closure(self, concept: str, extra: list[Fact] | None = None) -> dict[Prop, Answer]:
        """All properties derivable for ``concept`` with their status and support."""
        if extra is not None:
            return self._closure(concept, extra)
        cache = self.__dict__.setdefault("_closure_cache", {})
        if concept not in cache:
            cache[concept] = self._closure(concept, None)
        return dict(cache[concept])

    def _closure(self, concept: str, extra):
        pos: dict[str, list] = {}
        neg: dict[str, list] = {}
        for a in self._solve({concept}, extra):
            args = [x.string for x in a.arguments if x.type == clingo.SymbolType.String]
            if a.name in ("supp", "nsupp") and args[0] == concept:
                kind = str(a.arguments[3])
                target = pos if a.name == "supp" else neg
                target.setdefault(args[1], []).append((args[2], kind))
        out: dict[Prop, Answer] = {}
        for pid in set(pos) | set(neg):
            prop = self._props[pid]
            sup_p = [(anc, k, self._source(anc, prop)) for anc, k in pos.get(pid, [])]
            sup_n = [(anc, k, self._source(anc, prop)) for anc, k in neg.get(pid, [])]
            if sup_p and sup_n:
                out[prop] = Answer("conflict", sup_p + sup_n)
            elif sup_p:
                out[prop] = Answer("true", sup_p)
            else:
                out[prop] = Answer("false", sup_n)
        return out

    def _source(self, ancestor: str, prop: Prop) -> str:
        for f in self.facts_by_concept.get(ancestor, []):
            if f.prop.key == prop.key:
                return f.source
        return f"{ancestor}/?"

    def query(self, concept: str, prop: Prop) -> Answer:
        if concept not in self.parents:
            return Answer("unknown")
        for p, ans in self.closure(concept).items():
            if p.key == prop.key:
                return ans
        return Answer("unknown")

    def is_a(self, concept: str, ancestor: str) -> bool:
        return ancestor in self.ancestors_or_self(concept)

    def check_assertion(self, concept: str, prop: Prop, negated: bool = False) -> str:
        """Would asserting ``concept`` (not) has ``prop`` contradict the KB?

        Returns "consistent", "redundant" (already entailed) or "inconsistent".
        Defeasible knowledge can be overridden, so only strict clashes count.
        """
        ans = self.query(concept, prop)
        if ans.status == "unknown":
            return "consistent"
        entailed_pos = ans.status == "true"
        if entailed_pos != negated:
            return "redundant"
        return "inconsistent" if ans.strict else "consistent"
