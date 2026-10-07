"""FunGramKB as a graph for GraphRAG (conditions G1, G2, G4).

Meaning postulates are *not* flattened to triples: each property becomes a
predication node with role-labelled edges, which is the structural difference with
a generic KG that the paper must show (Method section, figure).

    (concept) --[self_role]--> (pred: event, strict|default, +/-) --[other_role]--> (filler)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import networkx as nx

from ..corel.nlg import sentence as _nlg_sentence
from ..corel.verbalize import _HEDGE, verbalise_fact, verbalise_isa
from ..reasoner.asp import Reasoner


def build_graph(reasoner: Reasoner, include_postulates: bool = True) -> nx.MultiDiGraph:
    kb = reasoner.kb
    g = nx.MultiDiGraph()
    for cid, c in kb.concepts.items():
        g.add_node(cid, kind="concept", stype=c.semantic_type)
    for child, parents in reasoner.parents.items():
        for p in parents:
            g.add_edge(child, p, key="isa", rel="IS-A")
    if include_postulates:
        for i, f in enumerate(reasoner.facts):
            pid = f"pred:{i}"
            g.add_node(pid, kind="predication", event=f.prop.event, strict=f.strict,
                       negated=f.negated, source=f.source, fact=f)
            g.add_edge(f.concept, pid, rel=f.prop.self_role)
            if f.prop.filler:
                g.add_edge(pid, f.prop.filler, rel=f.prop.other_role)
    return g


@dataclass
class Linearised:
    text: str
    n_tokens: int
    facts_used: int


def approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _corel_line(f) -> str:
    sign = "+" if f.strict else "*"
    neg = "n " if f.negated else ""
    other = f" ({f.prop.other_role}: {f.prop.filler})" if f.prop.filler else ""
    return f"{f.concept} {sign}[{neg}{f.prop.event} as {f.prop.self_role}{other}]"


def linearise_subgraph(
    reasoner: Reasoner,
    seeds: list[str],
    *,
    budget_tokens: int = 1500,
    hops_up: int = 6,
    mode: str = "full",  # "isa" (G1) | "full" (G2/G4)
    style: str = "nl",  # "nl" verbalised | "corel" compact formal lines
    lang: str = "en",
    filler_hops: int = 1,
) -> Linearised:
    """Collect IS-A chains and (optionally) postulates around the seed concepts.

    Ordering: IS-A chain of every seed first, then postulates of the seed itself,
    then of its ancestors from nearest to farthest. Stops at the token budget.
    """
    kb = reasoner.kb
    lines: list[str] = []
    seen_lines: set[str] = set()
    used = 0

    def add(line: str) -> bool:
        nonlocal used
        if line in seen_lines:
            return True
        cost = approx_tokens(line) + 1
        if used + cost > budget_tokens:
            return False
        lines.append(line)
        seen_lines.add(line)
        used += cost
        return True

    order: list[str] = []

    def chain(roots: list[str]) -> bool:
        for s in roots:
            frontier, depth = [s], 0
            while frontier and depth <= hops_up:
                nxt = []
                for c in frontier:
                    if c not in order:
                        order.append(c)
                    for p in sorted(reasoner.parents.get(c, ())):
                        if p.startswith("#"):
                            # metaconcepts carry no postulates; in NL mode they only spend budget
                            ok = add(f"{c} IS-A {p}") if style == "corel" else True
                        elif style == "corel":
                            ok = add(f"{c} IS-A {p}")
                        else:
                            ok = add(verbalise_isa(kb, c, p, lang))
                        if not ok:
                            return False
                        nxt.append(p)
                frontier, depth = nxt, depth + 1
        return True

    n_facts = 0

    def facts_of(concepts: list[str]) -> tuple[bool, list[str]]:
        nonlocal n_facts
        fillers: list[str] = []
        for c in concepts:
            for f in reasoner.facts_by_concept.get(c, []):
                if style == "corel":
                    line = _corel_line(f)
                elif f.prop.subj_role:
                    line = _nlg_sentence(kb, f.concept, f.prop, negated=f.negated, lang=lang,
                                         hedge=_HEDGE[(lang, f.strict)])
                    if line is None:  # not expressible in natural language: skip rather than garble
                        continue
                else:
                    line = verbalise_fact(kb, f, lang)
                if not add(line):
                    return False, fillers
                n_facts += 1
                for tok in re.split(r"[|^&]", f.prop.filler or ""):
                    tok = tok.strip().strip("()").split()
                    if tok and tok[-1] in kb.concepts and tok[-1] not in order and tok[-1] not in fillers:
                        fillers.append(tok[-1])
        return True, fillers

    if not chain(seeds):
        return Linearised("\n".join(lines), used, 0)
    if mode == "full":
        ring = list(order)
        for _ in range(filler_hops + 1):
            ok, fillers = facts_of(ring)
            if not ok or not fillers:
                break
            # next ring: concepts that fill the roles of facts already shown (GraphRAG expansion
            # along role edges), with their own IS-A chains and postulates
            start = len(order)
            if not chain(fillers):
                break
            ring = order[start:]
    return Linearised("\n".join(lines), used, n_facts)
