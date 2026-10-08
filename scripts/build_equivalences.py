"""Concept equivalences for N1P3 (exploratory): post-parse normalisation of COREL queries.

Two maps between FunGramKB concepts, derived from WordNet (never from the benchmark):

  noun -> quality     an entity concept whose noun is derivationally related to, or is the WordNet attribute
                      of, the adjective of a quality concept (violence -> VIOLENT_00; size -> SMALL_00, BIG_00).
                      Used to read "X involves violence" / "X has a small size" as BE_01 (X, quality).
  quality -> quality  quality concepts whose adjectives share a WordNet synset or are similar_to each other
                      (little ~ small). Used when the parser picks a near-synonymous quality.

Written as a table for expert review (column "approve (1/0)"; blank = accepted, 0 = rejected) and as JSON:

    python scripts/build_equivalences.py --kb data/processed/fungramkb.json \\
        --tsv docs/n1p3_equivalences.tsv --json data/extension/n1p3_equivalences.json
    python scripts/build_equivalences.py --from-tsv docs/n1p3_equivalences.tsv --json data/extension/n1p3_equivalences.json
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from fgkb_llm.controls.generic_kg import _wordnet
from fgkb_llm.kb.loaders import load_json

SENSES = 2  # most frequent WordNet senses per lemma


def build(kb) -> list[dict]:
    wn = _wordnet()
    qual_of = defaultdict(set)  # English adjective -> quality concepts
    for cid, c in kb.concepts.items():
        if c.semantic_type == "quality" and not cid.startswith("#"):
            for lem in kb.lemmas(cid, "en"):
                qual_of[lem.lower().replace(" ", "_")].add(cid)
    rows, seen = [], set()

    def add(kind, src, dst, via):
        if src != dst and (kind, src, dst) not in seen:
            seen.add((kind, src, dst))
            rows.append({"kind": kind, "source": src, "target": dst, "source_label": kb.label(src, "en"),
                         "target_label": kb.label(dst, "en"), "wordnet": via, "approve (1/0)": ""})

    for cid, c in sorted(kb.concepts.items()):
        if cid.startswith("#") or c.semantic_type != "entity":
            continue
        for lem in kb.lemmas(cid, "en"):
            for syn in wn.synsets(lem.replace(" ", "_"), pos="n")[:SENSES]:
                adjs = [(a, f"attribute {syn.name()}") for s in syn.attributes() for a in s.lemma_names()]
                for wl in syn.lemmas():
                    adjs += [(d.name(), f"derivation {wl.name()}->{d.name()}") for d in wl.derivationally_related_forms()
                             if d.synset().pos() in "as"]
                for adj, via in adjs:
                    for q in qual_of.get(adj.lower(), ()):
                        add("noun->quality", cid, q, via)
    for adj, qs in sorted(qual_of.items()):
        for q in sorted(qs):
            for syn in wn.synsets(adj, pos="a")[:SENSES] + wn.synsets(adj, pos="s")[:SENSES]:
                names = set(syn.lemma_names()) | {n for s in syn.similar_tos() for n in s.lemma_names()}
                for n in names:
                    for q2 in qual_of.get(n.lower(), ()):
                        add("quality->quality", q, q2, f"{syn.name()} ~ {n}")
    return rows


def to_json(rows) -> dict:
    out = {"noun->quality": defaultdict(list), "quality->quality": defaultdict(list)}
    for r in rows:
        if (r.get("approve (1/0)") or "").strip() == "0":
            continue
        out[r["kind"]][r["source"]].append(r["target"])
    return {k: dict(v) for k, v in out.items()}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", default="data/processed/fungramkb.json")
    ap.add_argument("--tsv", default="docs/n1p3_equivalences.tsv")
    ap.add_argument("--json", default="data/extension/n1p3_equivalences.json")
    ap.add_argument("--from-tsv", default=None, help="rebuild the JSON from a reviewed table")
    a = ap.parse_args(argv)
    if a.from_tsv:
        with open(a.from_tsv, encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh, delimiter="\t"))
    else:
        rows = build(load_json(a.kb))
        with open(a.tsv, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter="\t")
            w.writeheader()
            w.writerows(rows)
    eq = to_json(rows)
    Path(a.json).parent.mkdir(parents=True, exist_ok=True)
    Path(a.json).write_text(json.dumps(eq, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print({k: sum(map(len, v.values())) for k, v in eq.items()}, "->", a.json)


if __name__ == "__main__":
    main()
