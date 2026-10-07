"""Concept-level splits.

A fixed fraction of basic/terminal *entity* concepts is held out: they never
appear in LoRA training data (F1/F2). Items whose focus concept is held out go to
``test_unseen``; the rest of the test items go to ``test_seen``.
"""

from __future__ import annotations

import random

from ..kb.model import KnowledgeBase


def concept_split(kb: KnowledgeBase, unseen_fraction: float = 0.3, seed: int = 7) -> dict[str, str]:
    rng = random.Random(seed)
    pool = sorted(c.id for c in kb.concepts.values()
                  if c.semantic_type == "entity" and c.level in ("basic", "terminal"))
    rng.shuffle(pool)
    n_unseen = round(len(pool) * unseen_fraction)
    unseen = set(pool[:n_unseen])
    return {cid: ("unseen" if cid in unseen else "seen") for cid in kb.concepts}


def assign_item_splits(items, split_map: dict[str, str], dev_fraction: float = 0.1, seed: int = 7):
    rng = random.Random(seed)
    for it in items:
        unseen = any(split_map.get(c) == "unseen" for c in it.focus_concepts[:1])
        if unseen:
            it.split = "test_unseen"
        else:
            it.split = "dev" if rng.random() < dev_fraction else "test_seen"
    return items
