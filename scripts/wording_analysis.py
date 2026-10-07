"""Prompt robustness across wordings (W1 original, W2 rule-based, W3 paraphrase).

Reads result files of the original items (W1) and of their wordings (item ids "<base>@w2", "<base>@w3")
and reports, per model and condition: accuracy per wording on the items present in all wordings,
the largest drop from W1, and answer consistency (same answer in every wording). It also tests,
with a cluster bootstrap over EN/ES twin groups, whether the G2 - B1 and N1P - G2 differences hold in
every wording.

    python scripts/wording_analysis.py results/main.jsonl results/main_wordings.jsonl --report docs/wording_report.md
"""

from __future__ import annotations

import argparse
import collections
import json
import random

WORDINGS = ("w1", "w2", "w3")
CONTRASTS = [("G2", "B1"), ("N1P", "G2"), ("N1P2", "G2"), ("N1P2", "N1P"), ("G2", "G3")]


PAIR: dict[str, str] = {}  # base item id -> twin cluster (pair_id without the wording suffix)


def load(paths):
    rows = {}
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                iid = r["item_id"]
                base, _, w = iid.partition("@")
                rows[(r["model"], r["condition"], base, w or "w1")] = r
                PAIR.setdefault(base, str(r.get("pair_id") or base).partition("@")[0])
    return rows


def cluster_of(base_id: str) -> str:
    return PAIR.get(base_id, base_id)  # EN/ES twins share pair_id


def boot_diff(a: dict, b: dict, n=2000, seed=0):
    """Mean difference a - b (per item 0/1) with a 95 % bootstrap CI over twin clusters."""
    clusters = collections.defaultdict(list)
    for k, va in a.items():
        clusters[cluster_of(k)].append(va - b[k])
    keys = list(clusters)
    rng = random.Random(seed)
    stat = lambda ks: sum(sum(clusters[k]) for k in ks) / max(1, sum(len(clusters[k]) for k in ks))
    est = stat(keys)
    bs = sorted(stat([rng.choice(keys) for _ in keys]) for _ in range(n))
    return est, bs[int(0.025 * n)], bs[int(0.975 * n)]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+")
    ap.add_argument("--report", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--wordings", default=None,
                    help="wordings benchmark: W3 accuracy is also split by meta.subject_changed")
    a = ap.parse_args(argv)
    rows = load(a.results)
    models = sorted({k[0] for k in rows})
    conds = sorted({k[1] for k in rows})
    lines = ["# Prompt robustness across wordings", "",
             "| Model | Cond | W1 | W2 | W3 | max drop | consistency | n |", "|---|---|---|---|---|---|---|---|"]
    out = {}
    for m in models:
        for c in conds:
            bases = {k[2] for k in rows if k[0] == m and k[1] == c}
            present = [w for w in WORDINGS if any((m, c, b, w) in rows for b in bases)]
            common = [b for b in bases if all((m, c, b, w) in rows for w in present)]
            if not common or "w1" not in present or len(present) < 2:
                continue  # conditions run in one wording only are not part of the robustness analysis
            acc = {w: sum(rows[(m, c, b, w)]["pred"] == rows[(m, c, b, w)]["gold"] for b in common) / len(common)
                   for w in present}
            cons = sum(len({rows[(m, c, b, w)]["pred"] for w in present}) == 1 for b in common) / len(common)
            drop = max(acc["w1"] - acc[w] for w in present)
            out[f"{m}/{c}"] = {"acc": acc, "consistency": cons, "max_drop": drop, "n": len(common)}

            def cell(w, acc=acc):
                return f"{acc[w]:.3f}" if w in acc else "–"

            lines.append(f"| {m} | {c} | {cell('w1')} | {cell('w2')} | {cell('w3')} | {drop:+.3f} | {cons:.3f} | "
                         f"{len(common)} |")
    lines += ["", "| Model | Contrast | wording | diff [95 % CI] |", "|---|---|---|---|"]
    for m in models:
        for x, y in CONTRASTS:
            # the same items in every wording, so the rows of a contrast are comparable
            sets = []
            for w in WORDINGS:
                bx = {k[2] for k in rows if k[:2] == (m, x) and k[3] == w}
                by = {k[2] for k in rows if k[:2] == (m, y) and k[3] == w}
                if bx & by:
                    sets.append((w, bx & by))
            if len(sets) < 2:
                continue
            common = set.intersection(*(c for _, c in sets))
            for w, _ in sets:
                ax = {b: int(rows[(m, x, b, w)]["pred"] == rows[(m, x, b, w)]["gold"]) for b in common}
                ay = {b: int(rows[(m, y, b, w)]["pred"] == rows[(m, y, b, w)]["gold"]) for b in common}
                est, lo, hi = boot_diff(ax, ay)
                out[f"{m}/{x}-{y}/{w}"] = {"diff": est, "ci": [lo, hi], "n": len(common)}
                lines.append(f"| {m} | {x} − {y} | {w} | {100 * est:+.1f} [{100 * lo:+.1f}, {100 * hi:+.1f}] "
                             f"(n={len(common)}) |")
    if a.wordings:
        flags = {}
        with open(a.wordings, encoding="utf-8") as fh:
            for line in fh:
                it = json.loads(line)
                if it.get("meta", {}).get("wording") == "w3":
                    flags[it["meta"]["base_id"]] = bool(it["meta"].get("subject_changed"))
        lines += ["", "W3 by subject change (the paraphrase's grammatical subject is not the queried concept)", "",
                  "| Model | Cond | same subject: W1 / W3 (n) | subject changed: W1 / W3 (n) |", "|---|---|---|---|"]
        for m in models:
            for c in conds:
                cells = []
                for flag in (False, True):
                    bs = [b for b, f in flags.items() if f == flag and (m, c, b, "w1") in rows and (m, c, b, "w3") in rows]
                    if not bs:
                        cells.append("–")
                        continue
                    acc = {w: sum(rows[(m, c, b, w)]["pred"] == rows[(m, c, b, w)]["gold"] for b in bs) / len(bs)
                           for w in ("w1", "w3")}
                    cells.append(f"{acc['w1']:.3f} / {acc['w3']:.3f} ({len(bs)})")
                if cells != ["–", "–"]:
                    lines.append(f"| {m} | {c} | {cells[0]} | {cells[1]} |")
    text = "\n".join(lines)
    print(text)
    if a.report:
        with open(a.report, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main()
