"""Sensitivity of the main results to the NLG errors found in the faithfulness audit (v2).

The audit (docs/nlg_faithfulness_rater{1,2}.xlsx) found a few recurrent, pattern-detectable errors in the
generated questions and premises. This script flags every analysis item that shows one of them, drops the whole
EN/ES twin cluster of a flagged item, and repeats the confirmatory tests (H1, H2, H2-null, H3) per model.

Flag sets (cumulative):
  agreed  -- errors both raters marked: the light verb +DO_00 rendered as "deal with" / "comerciar con",
             "refugee" for the place +REFUGE_00, and a "many"/"muchos" quantifier absent from the queried filler.
  strict  -- agreed + the generic "something"/"algo" used for intermediate entities (rater 2 only).

    python scripts/nlg_sensitivity.py --results results/main.jsonl results/main_n1p3.jsonl \\
        --out results/nlg_sensitivity.json --report docs/nlg_sensitivity_report.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from main_analysis import _paired, analysis_items, confirmatory, load_rows

DO_LIGHT = re.compile(r"\bdeals? with\b|\bdealt with\b|\bdealing with\b|\bcomerci\w* con\b", re.IGNORECASE)
REFUGEE = re.compile(r"\brefugees?\b", re.IGNORECASE)
MANY = re.compile(r"\bmany\b|\bmuch[oa]s\b", re.IGNORECASE)
SOMETHING = re.compile(r"\bsomething\b|\balgo\b", re.IGNORECASE)


def _text(item) -> str:
    return " ".join(x for x in (item.question, item.premise, item.hypothesis) if x)


def _spurious_many(item) -> bool:
    if not MANY.search(_text(item)):
        return False
    prop = item.meta.get("prop") or []
    filler = str(prop[3]) if len(prop) > 3 else ""
    return not re.search(r"(^|[\s(^&|])m\s", filler)


def flags(item) -> set[str]:
    t, out = _text(item), set()
    if DO_LIGHT.search(t):
        out.add("do_light")
    if REFUGEE.search(t):
        out.add("refugee")
    if _spurious_many(item):
        out.add("spurious_many")
    if SOMETHING.search(t):
        out.add("something")
    return out


SETS = {"agreed": {"do_light", "refugee", "spurious_many"},
        "strict": {"do_light", "refugee", "spurious_many", "something"}}


def run(results, bench):
    items = analysis_items(bench)
    rows = load_rows(results)
    cluster = {i.id: i.pair_id or i.id for i in items}
    fl = {i.id: flags(i) for i in items}
    out = {"n_items": len(items), "n_clusters": len(set(cluster.values())),
           "flag_counts": {k: sum(k in f for f in fl.values()) for k in SETS["strict"]}, "sets": {}}
    for name, keys in SETS.items():
        bad_clusters = {cluster[i] for i, f in fl.items() if f & keys}
        keep_ids = {i for i in fl if cluster[i] not in bad_clusters}
        res = {"items_kept": len(keep_ids), "clusters_dropped": len(bad_clusters), "models": {}}
        for m in sorted({r["model"] for r in rows}):
            corr = {}
            for r in rows:
                if r["model"] == m and r["item_id"] in cluster:
                    corr.setdefault(r["condition"], {})[r["item_id"]] = int(r["pred"] == r["gold"])
            full = confirmatory(corr, cluster)
            sub = confirmatory(corr, cluster, lambda i, k=keep_ids: i in k)
            acc = {c: [float(np.mean(list(d.values()))),
                       float(np.mean([v for i, v in d.items() if i in keep_ids]))] for c, d in corr.items()}
            extra = {}
            if "N1P3" in corr and "N1P2" in corr:
                for lab, ids in (("full", set(cluster)), ("kept", keep_ids)):
                    extra[f"N1P3-N1P2 {lab}"] = _paired({i: v for i, v in corr["N1P2"].items() if i in ids},
                                                        {i: v for i, v in corr["N1P3"].items() if i in ids}, cluster)
            res["models"][m] = {"accuracy_full_kept": acc, "tests_full": full, "tests_kept": sub, "extra": extra}
        out["sets"][name] = res
    return out


def _fmt(t):
    if not t:
        return "--"
    p = t.get("p_holm", t.get("p_two_sided", t.get("p_cluster_t")))
    return f"{100 * t['diff']:+.1f} (p={p:.3g})"


def report(res) -> str:
    lines = ["# Sensitivity to NLG errors (faithfulness audit v2)", "",
             f"Analysis set: {res['n_items']} items, {res['n_clusters']} twin clusters. Items flagged: "
             + ", ".join(f"{k} {v}" for k, v in res["flag_counts"].items()) + ".", ""]
    for name, s in res["sets"].items():
        lines += [f"## Set '{name}': {s['clusters_dropped']} clusters dropped, {s['items_kept']} items kept", "",
                  "| model | test | full | kept |", "|---|---|---|---|"]
        for m, r in s["models"].items():
            for k in r["tests_full"]:
                if k.startswith("H2-null"):
                    f, g = r["tests_full"][k], r["tests_kept"][k]
                    lines.append(f"| {m} | {k} | {100 * f['diff']:+.1f}, equiv={f['equivalent']} | "
                                 f"{100 * g['diff']:+.1f}, equiv={g['equivalent']} |")
                else:
                    lines.append(f"| {m} | {k} | {_fmt(r['tests_full'][k])} | {_fmt(r['tests_kept'][k])} |")
            if r["extra"]:
                lines.append(f"| {m} | N1P3-N1P2 (exploratory) | {_fmt(r['extra']['N1P3-N1P2 full'])} | "
                             f"{_fmt(r['extra']['N1P3-N1P2 kept'])} |")
        lines += ["", "Accuracy full -> kept:", ""]
        for m, r in s["models"].items():
            lines.append(f"- {m}: " + "; ".join(f"{c} {100 * a:.1f}->{100 * b:.1f}"
                                                for c, (a, b) in sorted(r["accuracy_full_kept"].items())))
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", nargs="+", required=True)
    ap.add_argument("--bench", default="data/processed/fgkb_reason_main.jsonl")
    ap.add_argument("--out", default="results/nlg_sensitivity.json")
    ap.add_argument("--report", default="docs/nlg_sensitivity_report.md")
    a = ap.parse_args(argv)
    res = run(a.results, a.bench)
    Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    Path(a.report).write_text(report(res), encoding="utf-8")
    print(report(res))


if __name__ == "__main__":
    main()
