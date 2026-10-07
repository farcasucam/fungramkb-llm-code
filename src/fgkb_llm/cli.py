"""Command-line entry point: ``fgkb <command>``.

    fgkb check-kb   --kb data/processed/fungramkb.json
    fgkb bench      --kb ... --out data/processed/fgkb_reason.jsonl [--balance configs/bench.yaml]
    fgkb sft-data   --kb ... --out data/processed/sft_train.jsonl
    fgkb run        --config configs/experiment.yaml
    fgkb report     results/*.jsonl --paper paper
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def main(argv=None):
    ap = argparse.ArgumentParser(prog="fgkb")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check-kb", help="validate KB structure and parse every meaning postulate")
    p.add_argument("--kb", required=True)

    p = sub.add_parser("bench", help="generate FGKB-Reason")
    p.add_argument("--kb", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--balance", help="YAML with per-task target counts")
    p.add_argument("--unseen", type=float, default=0.3)
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--deep", action="store_true", help="also generate the deep-reasoning suite (P13-P15)")

    p = sub.add_parser("sft-data", help="build LoRA training data from seen concepts")
    p.add_argument("--kb", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--unseen", type=float, default=0.3)

    p = sub.add_parser("run", help="run an experiment config")
    p.add_argument("--config", required=True)
    p.add_argument("--redo", help="comma-separated conditions to run again (old rows backed up and removed)")

    p = sub.add_parser("report", help="tables and figures for the paper")
    p.add_argument("results", nargs="+")
    p.add_argument("--paper", default="paper")

    a = ap.parse_args(argv)

    if a.cmd == "check-kb":
        from .kb.loaders import load_json, validate
        from .reasoner.asp import Reasoner

        kb = load_json(a.kb)
        problems = validate(kb)
        r = Reasoner(kb)
        n_mp = sum(1 for _ in kb.with_postulates())
        print(json.dumps({
            "concepts": len(kb.concepts), "lexical_units": len(kb.lexicon), "scripts": len(kb.scripts),
            "postulates": n_mp, "postulate_parse_errors": len(r.parse_errors), "facts": len(r.facts),
            "structural_problems": problems[:20], "parse_error_examples": dict(list(r.parse_errors.items())[:10]),
        }, indent=2, ensure_ascii=False))

    elif a.cmd == "bench":
        from .bench.generate import BenchmarkGenerator, balance, describe
        from .bench.schema import write_jsonl
        from .bench.splits import assign_item_splits, concept_split
        from .kb.loaders import load_json

        kb = load_json(a.kb)
        items = BenchmarkGenerator(kb, seed=a.seed).generate_all()
        if a.deep:
            from .bench.deep import DeepSuite

            items += DeepSuite(kb, seed=a.seed).generate()
        assign_item_splits(items, concept_split(kb, a.unseen))
        if a.balance:
            items = balance(items, yaml.safe_load(Path(a.balance).read_text(encoding="utf-8"))["per_task"])
        write_jsonl(items, a.out)
        print(json.dumps(describe(items), indent=2, ensure_ascii=False))

    elif a.cmd == "sft-data":
        from .bench.splits import concept_split
        from .finetune.make_sft import build_sft
        from .kb.loaders import load_json

        kb = load_json(a.kb)
        n = build_sft(kb, concept_split(kb, a.unseen), a.out)
        print(f"{n} SFT examples -> {a.out}")

    elif a.cmd == "run":
        from .runner import run

        print(run(a.config, redo=a.redo.split(",") if a.redo else None))

    elif a.cmd == "report":
        from .analysis.report import build_all

        build_all(a.results, a.paper)
        print(f"tables and figures written under {a.paper}/")


if __name__ == "__main__":
    main()
