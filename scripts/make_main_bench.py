"""Benchmark for the preregistered main study (confirmatory), generated with a new seed.

The knowledge base is finite, so items about real concepts (deep_real, ablation, counterfactual,
undet_control) largely coincide with the pilot benchmark, while pseudoword blocks (novel, exceptions)
and most 'undetermined' items are new. To keep the confirmatory analysis clean:

* every twin group whose question also occurs in the pilot benchmark is tagged
  ``meta["pilot_overlap"] = "dev" | "test"`` (else ``"none"``), so a sensitivity analysis can be run on
  the pilot-disjoint items;
* groups that overlap a pilot *dev* item are moved to the dev split: the N1P parser was tuned on the
  pilot dev split, so those items must not count as test evidence.

The concept split (seen / unseen) is unchanged (fixed seed in bench/splits.py), as LoRA training data
depend on it.

    python scripts/make_main_bench.py --kb data/processed/fungramkb.json \\
        --pilot data/processed/fgkb_reason.jsonl --out data/processed/fgkb_reason_main.jsonl --seed 2027
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from fgkb_llm.bench.contrast import contrast_subset
from fgkb_llm.bench.deep import DeepSuite
from fgkb_llm.bench.generate import BenchmarkGenerator, describe
from fgkb_llm.bench.schema import read_jsonl, write_jsonl
from fgkb_llm.bench.splits import assign_item_splits, concept_split
from fgkb_llm.kb.loaders import load_json


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", default="data/processed/fungramkb.json")
    ap.add_argument("--pilot", default="data/processed/fgkb_reason.jsonl")
    ap.add_argument("--out", default="data/processed/fgkb_reason_main.jsonl")
    ap.add_argument("--seed", type=int, default=2027)
    ap.add_argument("--unseen", type=float, default=0.3)
    ap.add_argument("--summary", default="docs/main_bench_summary.json")
    a = ap.parse_args(argv)

    kb = load_json(a.kb)
    items = BenchmarkGenerator(kb, seed=a.seed).generate_all() + DeepSuite(kb, seed=a.seed).generate()
    assign_item_splits(items, concept_split(kb, a.unseen))

    pilot = read_jsonl(a.pilot)
    pilot_split = {}
    for it in pilot:
        for text in (it.question, it.hypothesis):
            # an item seen in pilot dev anywhere wins over a test occurrence
            if text and pilot_split.get(text) != "dev":
                pilot_split[text] = "dev" if it.split == "dev" else "test"

    groups = collections.defaultdict(list)
    for it in items:
        groups[it.pair_id or it.id].append(it)
    moved = 0
    for members in groups.values():
        hits = {pilot_split.get(t) for m in members for t in (m.question, m.hypothesis) if t} - {None}
        tag = "dev" if "dev" in hits else ("test" if hits else "none")
        for m in members:
            m.meta["pilot_overlap"] = tag
            if tag == "dev" and m.split != "dev":
                m.split = "dev"
                moved += 1
    for it in items:
        it.id = f"main-{it.id}"
        it.meta["bench_seed"] = a.seed
    write_jsonl(items, a.out)

    deep_c = [i for i in contrast_subset([i for i in items if i.task == "deep"]) if i.lang == "en"]
    by_block = collections.defaultdict(collections.Counter)
    for i in deep_c:
        by_block[i.meta.get("block")][i.meta["pilot_overlap"]] += 1
    summary = {
        "seed": a.seed, "items": len(items), "moved_to_dev_for_pilot_dev_overlap": moved,
        "deep_contrast_en": len(deep_c),
        "deep_contrast_en_labels": collections.Counter(i.gold for i in deep_c),
        "deep_contrast_en_splits": collections.Counter(i.split for i in deep_c),
        "deep_contrast_en_pilot_overlap_by_block": {b: dict(c) for b, c in sorted(by_block.items())},
        "describe": describe(items),
    }
    Path(a.summary).write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=dict), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "describe"}, indent=2, ensure_ascii=False, default=dict))


if __name__ == "__main__":
    main()
