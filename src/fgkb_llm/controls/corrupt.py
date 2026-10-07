"""Control G4: a corrupted KB with the same format but shuffled content.

Meaning postulates are permuted among concepts of the same semantic type and
ontological level (seeded), and the definiendum identifier inside each postulate
is rewritten to the receiving concept. The ontology (IS-A) is left intact, so G4
differs from G2 only in postulate *content*.
"""

from __future__ import annotations

import copy
import random

from ..kb.model import KnowledgeBase


def corrupt_postulates(kb: KnowledgeBase, seed: int = 13) -> KnowledgeBase:
    rng = random.Random(seed)
    out = copy.deepcopy(kb)
    groups: dict[tuple[str, str], list[str]] = {}
    for c in out.concepts.values():
        if c.meaning_postulate:
            groups.setdefault((c.semantic_type, c.level), []).append(c.id)
    for ids in groups.values():
        if len(ids) < 2:
            continue
        perm = ids[:]
        # derangement: no concept keeps its own postulate
        for _ in range(100):
            rng.shuffle(perm)
            if all(a != b for a, b in zip(ids, perm)):
                break
        originals = {i: kb.concepts[i].meaning_postulate for i in ids}
        for target, donor in zip(ids, perm):
            out.concepts[target].meaning_postulate = originals[donor].replace(donor, target)
    out.version = f"{kb.version}+corrupt{seed}"
    return out
