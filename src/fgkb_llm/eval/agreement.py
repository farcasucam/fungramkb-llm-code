"""Inter-annotator agreement for the human validation sample (400 items, 2 annotators)."""

from __future__ import annotations

import csv
import random
from collections import Counter
from pathlib import Path


def cohen_kappa(a: list[str], b: list[str]) -> float:
    assert len(a) == len(b) and a
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def annotation_sheet(items, path: str | Path, n: int = 400, seed: int = 1) -> None:
    """Stratified sample (by task and template) exported as CSV for annotators.
    Annotators fill 'label' (their answer) and 'ok' (1 = item well formed)."""
    rng = random.Random(seed)
    strata: dict = {}
    for it in items:
        strata.setdefault((it.task, it.template), []).append(it)
    per = max(1, n // max(1, len(strata)))
    sample = []
    for group in strata.values():
        rng.shuffle(group)
        sample += group[:per]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["item_id", "task", "template", "lang", "question", "options", "label", "ok", "comment"])
        for it in sample[:n]:
            w.writerow([it.id, it.task, it.template, it.lang, it.question, " | ".join(it.options), "", "", ""])


def template_agreement(sheet_a: str, sheet_b: str, gold: dict[str, str]) -> dict[str, dict]:
    """Per-template kappa between annotators and accuracy of each against the KB gold.
    Templates with kappa < 0.7 are discarded (project protocol)."""
    def read(p):
        with open(p, encoding="utf-8") as fh:
            return {r["item_id"]: r for r in csv.DictReader(fh)}
    A, B = read(sheet_a), read(sheet_b)
    by_t: dict = {}
    for iid in set(A) & set(B):
        by_t.setdefault(A[iid]["template"], []).append(iid)
    out = {}
    for t, ids in by_t.items():
        la, lb = [A[i]["label"] for i in ids], [B[i]["label"] for i in ids]
        out[t] = {"n": len(ids), "kappa": cohen_kappa(la, lb),
                  "acc_a": sum(A[i]["label"] == gold.get(i) for i in ids) / len(ids),
                  "acc_b": sum(B[i]["label"] == gold.get(i) for i in ids) / len(ids),
                  "keep": cohen_kappa(la, lb) >= 0.7}
    return out
