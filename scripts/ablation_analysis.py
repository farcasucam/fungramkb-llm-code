"""S3 (lexicon-expanded KB) and S4 (G2 component ablations) of the main study (analysis plan, section 8).

    python scripts/ablation_analysis.py --base results/main.jsonl results/main_wordings.jsonl \\
        --s3 results/main_s3_lex.jsonl results/main_s3_lex_wordings.jsonl --s4 results/main_s4.jsonl \\
        --bench data/processed/fgkb_reason_main.jsonl --report docs/main_ablations_report.md \\
        --out results/main_ablations.json

S3: accuracy difference lexicon-expanded minus base KB, per model, condition (G2, N1P2) and wording.
S4: accuracy difference G2 with one component removed minus full G2 (Qwen), overall and on the blocks the
component should matter for (exceptions for the hedges; deep inheritance for the fillers).
Differences with 95 % cluster-bootstrap CIs over EN/ES twin clusters and two-sided cluster t-tests.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wording_analysis import PAIR, boot_diff, load

from fgkb_llm.bench.schema import read_jsonl


def _p_two_sided(a: dict, b: dict) -> float:
    by = defaultdict(list)
    for k, v in a.items():
        by[PAIR.get(k, k)].append(v - b[k])
    d = np.array([np.mean(v) for v in by.values()])
    return float(stats.ttest_1samp(d, 0).pvalue) if len(d) > 2 and d.std() > 0 else 1.0


def contrast(x: dict, y: dict) -> dict | None:
    common = sorted(set(x) & set(y))
    if len(common) < 10:
        return None
    a = {k: x[k] for k in common}
    b = {k: y[k] for k in common}
    est, lo, hi = boot_diff(a, b)
    return {"diff": est, "ci": [lo, hi], "p": _p_two_sided(a, b), "n": len(common),
            "acc_x": float(np.mean(list(a.values()))), "acc_y": float(np.mean(list(b.values())))}


def correct(rows: dict, model: str, cond: str, wording: str) -> dict:
    return {k[2]: int(r["pred"] == r["gold"]) for k, r in rows.items()
            if k[0] == model and k[1] == cond and k[3] == wording}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", nargs="+", required=True)
    ap.add_argument("--s3", nargs="*", default=[])
    ap.add_argument("--s4", nargs="*", default=[])
    ap.add_argument("--bench", default="data/processed/fgkb_reason_main.jsonl")
    ap.add_argument("--report", default="docs/main_ablations_report.md")
    ap.add_argument("--out", default="results/main_ablations.json")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    base = load(a.base)
    blocks = {i.id: i.meta.get("block", "") for i in read_jsonl(a.bench)}
    out, L = {"S3": {}, "S4": {}}, ["# Main study: ablations S3 and S4", ""]

    if a.s3:
        lex = load(a.s3)
        L += ["## S3: lexicon-expanded KB minus base KB", "",
              "| Model | Cond | Wording | base | lex | diff [95 % CI] | p | n |", "|---|---|---|---|---|---|---|---|"]
        for m in sorted({k[0] for k in lex}):
            for c in sorted({k[1] for k in lex if k[0] == m}):
                for w in ("w1", "w2", "w3"):
                    t = contrast(correct(lex, m, c, w), correct(base, m, c, w))
                    if t is None:
                        continue
                    out["S3"][f"{m}/{c}/{w}"] = t
                    L.append(f"| {m} | {c} | {w} | {t['acc_y']:.3f} | {t['acc_x']:.3f} | {100 * t['diff']:+.1f} "
                             f"[{100 * t['ci'][0]:+.1f}, {100 * t['ci'][1]:+.1f}] | {t['p']:.3f} | {t['n']} |")
        L.append("")

    if a.s4:
        abl = load(a.s4)
        L += ["## S4: G2 with one component removed minus full G2", "",
              "| Model | Ablation | Items | full G2 | ablated | diff [95 % CI] | p | n |", "|---|---|---|---|---|---|---|---|"]
        for mm in sorted({k[0] for k in abl}):
            m, _, ab = mm.partition("@")
            full = correct(base, m, "G2", "w1")
            part = correct(abl, mm, "G2", "w1")
            for label, keep in (("all", lambda i: True), ("exceptions", lambda i: blocks.get(i) == "exceptions"),
                                ("deep_real", lambda i: blocks.get(i) == "deep_real"),
                                ("novel", lambda i: blocks.get(i) == "novel")):
                t = contrast({k: v for k, v in part.items() if keep(k)}, {k: v for k, v in full.items() if keep(k)})
                if t is None:
                    continue
                out["S4"][f"{m}/{ab}/{label}"] = t
                L.append(f"| {m} | {ab} | {label} | {t['acc_y']:.3f} | {t['acc_x']:.3f} | {100 * t['diff']:+.1f} "
                         f"[{100 * t['ci'][0]:+.1f}, {100 * t['ci'][1]:+.1f}] | {t['p']:.3f} | {t['n']} |")
    text = "\n".join(L)
    print(text)
    Path(a.report).write_text(text + "\n", encoding="utf-8")
    Path(a.out).write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
