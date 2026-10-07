"""Pre-registered analysis of the go/no-go pilot (deep contrast subset).

    python scripts/pilot_analysis.py --results results/pilot.jsonl --bench data/processed/fgkb_reason.jsonl \
        --out results/pilot_analysis.json --report docs/pilot_report.md

Primary hypothesis H1 (one test per model): accuracy(G2) > accuracy(B1) on the deep contrast subset.
Secondary (Holm over the family): G2 > G1 (postulates add over taxonomy), G2 > G4 (the *right* knowledge,
not any knowledge), G2 > R1 (structure over text RAG), N1 > G2, G2 > B1 on test_unseen only.

Reasoning-not-recall diagnostics (descriptive, with bootstrap CIs):
  * evidence sensitivity: on ablation pairs (intact item vs the same question with one required fact
    removed), the share of pairs where the model answers the intact item correctly AND switches to
    "undetermined" when the evidence is removed;
  * counterfactual compliance: accuracy on counterfactual "affected" items (the prior says yes, the
    scenario says no) vs their controls;
  * exception handling: accuracy on exception and exception-of-exception items;
  * novel-concept transfer: accuracy on pseudoword concepts (no pre-training exposure possible).
Test: paired cluster t-test over item clusters (EN/ES twins), plus exact McNemar on EN items.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from fgkb_llm.bench.contrast import contrast_subset
from fgkb_llm.bench.schema import read_jsonl

SECONDARY = [("G2", "G1"), ("G2", "G3"), ("G2", "G4"), ("G2", "R1"), ("N1", "G2")]
# reported without Holm (not in the preregistered family): H2's "G4 does not beat G1" and the N1R variant
EXPLORATORY = [("G4", "G1"), ("N1R", "N1"), ("N1R", "G2"), ("N1P", "N1R"), ("N1P", "G2")]
LABELS = ("yes", "no", "undetermined")


def _balanced(golds, preds) -> tuple[float, float]:
    """Balanced accuracy (mean recall per gold label) and macro-F1 over yes/no/undetermined."""
    rec, f1 = [], []
    for g in LABELS:
        tp = sum(1 for x, y in zip(golds, preds) if x == g and y == g)
        fn = sum(1 for x, y in zip(golds, preds) if x == g and y != g)
        fp = sum(1 for x, y in zip(golds, preds) if x != g and y == g)
        if tp + fn:
            rec.append(tp / (tp + fn))
        f1.append(2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 0.0)
    return (float(np.mean(rec)) if rec else float("nan")), float(np.mean(f1))


def _paired(correct_a: dict, correct_b: dict, cluster: dict):
    """Cluster-level paired test of b - a over items answered under both conditions."""
    from scipy import stats

    common = sorted(set(correct_a) & set(correct_b))
    if len(common) < 10:
        return None
    by_c = defaultdict(list)
    for i in common:
        by_c[cluster[i]].append(correct_b[i] - correct_a[i])
    diffs = np.array([np.mean(v) for v in by_c.values()])
    t = stats.ttest_1samp(diffs, 0, alternative="greater")
    en = [i for i in common if i.endswith("-en")]
    b01 = sum(1 for i in en if correct_a[i] and not correct_b[i])
    b10 = sum(1 for i in en if not correct_a[i] and correct_b[i])
    mcn = stats.binomtest(b10, b01 + b10, 0.5, alternative="greater").pvalue if b01 + b10 else 1.0
    rng = np.random.default_rng(0)
    boot = [rng.choice(diffs, len(diffs)).mean() for _ in range(2000)]
    return {"n_items": len(common), "clusters": len(diffs), "acc_a": float(np.mean([correct_a[i] for i in common])),
            "acc_b": float(np.mean([correct_b[i] for i in common])), "diff": float(diffs.mean()),
            "ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
            "p_cluster_t": float(t.pvalue), "p_mcnemar_en": float(mcn), "discordant_en": [b01, b10]}


def _holm(pvals: dict) -> dict:
    order = sorted(pvals, key=pvals.get)
    m, out, running = len(order), {}, 0.0
    for k, name in enumerate(order):
        running = max(running, min(1.0, (m - k) * pvals[name]))
        out[name] = running
    return out


def analyse(rows, items):
    by_id = {i.id: i for i in items}
    cset = {i.id for i in contrast_subset(items)}
    cluster = {i.id: i.pair_id or i.id for i in items}
    res = {}
    models = sorted({r["model"] for r in rows})
    for m in models:
        corr = defaultdict(dict)  # cond -> item -> 0/1
        pred = defaultdict(dict)
        for r in rows:
            if r["model"] == m and r["item_id"] in by_id:
                corr[r["condition"]][r["item_id"]] = int(r["pred"] == r["gold"])
                pred[r["condition"]][r["item_id"]] = r["pred"]
        out = {"accuracy": {}, "by_block": {}, "tests": {}, "diagnostics": {}}
        for c, d in corr.items():
            cs = [v for i, v in d.items() if i in cset]
            ids = [i for i in d if i in cset]
            bal, mf1 = _balanced([by_id[i].gold for i in ids], [pred[c][i] for i in ids])
            out["accuracy"][c] = {"contrast": float(np.mean(cs)) if cs else None, "n": len(cs),
                                  "all_deep": float(np.mean(list(d.values()))), "balanced": bal, "macro_f1": mf1,
                                  "undetermined_rate": float(np.mean([pred[c][i] == "undetermined" for i in ids]))
                                  if ids else None}
            blocks = defaultdict(list)
            for i, v in d.items():
                blocks[by_id[i].meta.get("block", by_id[i].task)].append(v)
            out["by_block"][c] = {b: float(np.mean(v)) for b, v in blocks.items()}
        def sub(c, corr=corr):
            return {i: v for i, v in corr.get(c, {}).items() if i in cset}

        if "G2" in corr and "B1" in corr:
            out["tests"]["H1 G2>B1"] = _paired(sub("B1"), sub("G2"), cluster)
            unseen = {i: v for i, v in sub("G2").items() if by_id[i].split == "test_unseen"}
            out["tests"]["G2>B1 unseen"] = _paired({i: v for i, v in sub("B1").items() if i in unseen}, unseen, cluster)
        fam = {}
        for b, a in SECONDARY:
            if a in corr and b in corr:
                t = _paired(sub(a), sub(b), cluster)
                out["tests"][f"{b}>{a}"] = t
                if t:
                    fam[f"{b}>{a}"] = t["p_cluster_t"]
        for k, p in _holm(fam).items():
            out["tests"][k]["p_holm"] = p
        for b, a in EXPLORATORY:
            if a in corr and b in corr:
                out["tests"][f"{b}>{a} (exploratory)"] = _paired(sub(a), sub(b), cluster)
        # diagnostics
        for c in corr:
            p = pred[c]
            sens = []
            for it in items:
                if it.meta.get("block") == "ablation" and it.id in p:
                    twin = it.id.replace("ablation", "deep_real")
                    if twin in p:
                        sens.append(int(p[twin] == by_id[twin].gold and p[it.id] == "undetermined"))
            cf = [corr[c][i] for i in corr[c] if by_id[i].meta.get("cf_kind") == "affected"]
            cfc = [corr[c][i] for i in corr[c] if by_id[i].meta.get("cf_kind") == "control"]
            exc = [corr[c][i] for i in corr[c] if by_id[i].meta.get("block") == "exceptions"]
            nov = [corr[c][i] for i in corr[c] if by_id[i].meta.get("block") == "novel"]
            out["diagnostics"][c] = {
                "evidence_sensitivity": float(np.mean(sens)) if sens else None, "n_ablation_pairs": len(sens),
                "counterfactual_affected": float(np.mean(cf)) if cf else None,
                "counterfactual_control": float(np.mean(cfc)) if cfc else None,
                "exceptions": float(np.mean(exc)) if exc else None, "novel": float(np.mean(nov)) if nov else None}
        res[m] = out
    return res


def render(res) -> str:
    L = ["# Pilot analysis (deep contrast subset)", ""]
    for m, o in res.items():
        L += [f"## {m}", "", "| Condition | acc (contrast) | balanced acc | macro-F1 | % undetermined | n |",
              "|---|---|---|---|---|---|"]
        for c, v in sorted(o["accuracy"].items()):
            acc = "–" if v["contrast"] is None else f"{v['contrast']:.3f}"
            L.append(f"| {c} | {acc} | {v['balanced']:.3f} | {v['macro_f1']:.3f} | {v['undetermined_rate']:.2f} | {v['n']} |")
        L += ["", "| Test | Δ | 95 % CI | p (cluster t) | p Holm | p McNemar EN |", "|---|---|---|---|---|---|"]
        for k, t in o["tests"].items():
            if t:
                L.append(f"| {k} | {t['diff']:+.3f} | [{t['ci95'][0]:+.3f}, {t['ci95'][1]:+.3f}] | {t['p_cluster_t']:.4f} | "
                         f"{t.get('p_holm', float('nan')):.4f} | {t['p_mcnemar_en']:.4f} |")
        L += ["", "| Condition | evidence sensitivity | CF affected | CF control | exceptions | novel |", "|---|---|---|---|---|---|"]
        def f(x):
            return "–" if x is None else f"{x:.3f}"

        for c, d in sorted(o["diagnostics"].items()):
            L.append(f"| {c} | {f(d['evidence_sensitivity'])} | {f(d['counterfactual_affected'])} | "
                     f"{f(d['counterfactual_control'])} | {f(d['exceptions'])} | {f(d['novel'])} |")
        L.append("")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", nargs="+", required=True)
    ap.add_argument("--bench", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", required=True)
    a = ap.parse_args(argv)
    rows = []
    for p in a.results:
        rows += [json.loads(line) for line in Path(p).read_text(encoding="utf-8").splitlines() if line.strip()]
    items = [i for i in read_jsonl(a.bench) if i.task == "deep"]
    res = analyse(rows, items)
    Path(a.out).write_text(json.dumps(res, indent=2), encoding="utf-8")
    Path(a.report).write_text(render(res), encoding="utf-8")
    print(render(res))


if __name__ == "__main__":
    main()
