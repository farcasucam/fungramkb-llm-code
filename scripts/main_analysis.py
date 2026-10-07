"""Confirmatory analysis of the main study, as frozen in docs/analysis_plan.md (git tag prereg-v1).

    python scripts/main_analysis.py --results results/main.jsonl --bench data/processed/fgkb_reason_main.jsonl \\
        --out results/main_analysis.json --report docs/main_report.md --long results/main_long.csv

Analysis set: deep contrast subset balanced over test_seen + test_unseen + dev, restricted to the test splits
(the same items the main configs run). Clustering unit: pair_id (EN/ES twins).

Section 5 of the plan:
  H1   G2 > B1, one-sided paired cluster t-test per model; supported if p < .05 in >= 2 of the 3 models
  H1u  G2 > B1 on test_unseen
  H2   Holm family per model: G2 > G1, G2 > G3, G2 > G4, G2 > R1 (one-sided)
  H2-null  G4 vs G1: TOST, margin +-3 points, 90 % CI
  H3   N1P2 vs G2, two-sided
Section 7: diagnostics (evidence sensitivity, counterfactuals, exceptions, novel concepts, depth).
Section 8: S1 pilot-disjoint items, S2 EN / ES, S5 balanced accuracy and macro-F1.
The pooled logistic mixed model is fitted in R (scripts/main_glmm.R) on the long table written with --long;
--glmm-python fits the statsmodels fallback (BinomialBayesMixedGLM) instead.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pilot_analysis import _balanced, _holm, _paired

from fgkb_llm.bench.contrast import contrast_subset
from fgkb_llm.bench.schema import read_jsonl

TEST = ("test_seen", "test_unseen")
H2 = [("G2", "G1"), ("G2", "G3"), ("G2", "G4"), ("G2", "R1")]
MARGIN = 0.03
ALPHA = 0.05


def analysis_items(bench: str):
    pool = [i for i in read_jsonl(bench) if i.task == "deep" and i.split in (*TEST, "dev")]
    return [i for i in contrast_subset(pool) if i.split in TEST]


def load_rows(paths):
    rows = {}
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                rows[(r["model"], r["condition"], r["item_id"])] = r  # a later file overrides (reruns)
    return list(rows.values())


def _cluster_diffs(a: dict, b: dict, cluster: dict) -> np.ndarray:
    by_c = defaultdict(list)
    for i in sorted(set(a) & set(b)):
        by_c[cluster[i]].append(b[i] - a[i])
    return np.array([np.mean(v) for v in by_c.values()])


def tost(a: dict, b: dict, cluster: dict, margin: float = MARGIN) -> dict:
    """Equivalence of b and a within +-margin: two one-sided cluster t-tests; 90 % CI."""
    d = _cluster_diffs(a, b, cluster)
    n, m, se = len(d), d.mean(), d.std(ddof=1) / np.sqrt(len(d))
    p_lower = stats.t.sf((m + margin) / se, n - 1)  # H0: diff <= -margin
    p_upper = stats.t.cdf((m - margin) / se, n - 1)  # H0: diff >= +margin
    half = stats.t.ppf(0.95, n - 1) * se
    p_greater = stats.t.sf(m / se, n - 1)  # "G4 does not exceed G1": also report the one-sided superiority test
    return {"diff": float(m), "ci90": [float(m - half), float(m + half)], "margin": margin, "clusters": n,
            "p_tost": float(max(p_lower, p_upper)), "equivalent": bool(max(p_lower, p_upper) < ALPHA),
            "p_b_greater": float(p_greater)}


def two_sided(a: dict, b: dict, cluster: dict) -> dict | None:
    t = _paired(a, b, cluster)
    if t is None:
        return None
    d = _cluster_diffs(a, b, cluster)
    t["p_two_sided"] = float(stats.ttest_1samp(d, 0).pvalue)
    return t


def boot_metric_diff(items, pred_a, pred_b, cluster, fn, n=2000, seed=0):
    """Difference fn(b) - fn(a) of a label-level metric (balanced accuracy, macro-F1), cluster bootstrap."""
    ids = [i.id for i in items if i.id in pred_a and i.id in pred_b]
    gold = {i.id: i.gold for i in items}
    groups = defaultdict(list)
    for i in ids:
        groups[cluster[i]].append(i)
    keys = list(groups)

    def stat(ks):
        sel = [i for k in ks for i in groups[k]]
        g = [gold[i] for i in sel]
        return fn(g, [pred_b[i] for i in sel]) - fn(g, [pred_a[i] for i in sel])

    rng = np.random.default_rng(seed)
    est = stat(keys)
    bs = sorted(stat([keys[j] for j in rng.integers(0, len(keys), len(keys))]) for _ in range(n))
    return {"diff": float(est), "ci95": [float(bs[int(0.025 * n)]), float(bs[int(0.975 * n)])], "n": len(ids)}


def confirmatory(corr, cluster, keep=lambda i: True):
    """H1, H1u, H2 (Holm), H2-null (TOST) and H3 on the items accepted by ``keep``."""

    def sub(c):
        return {i: v for i, v in corr.get(c, {}).items() if keep(i)}

    out = {}
    if "G2" in corr and "B1" in corr:
        out["H1 G2>B1"] = _paired(sub("B1"), sub("G2"), cluster)
    fam = {}
    for b, a in H2:
        if a in corr and b in corr:
            t = _paired(sub(a), sub(b), cluster)
            out[f"H2 {b}>{a}"] = t
            if t:
                fam[f"H2 {b}>{a}"] = t["p_cluster_t"]
    for k, p in _holm(fam).items():
        out[k]["p_holm"] = p
    if "G4" in corr and "G1" in corr:
        out["H2-null G4~G1 (TOST)"] = tost(sub("G1"), sub("G4"), cluster)
    if "N1P2" in corr and "G2" in corr:
        out["H3 N1P2 vs G2"] = two_sided(sub("G2"), sub("N1P2"), cluster)
    return out


def analyse(rows, items):
    by_id = {i.id: i for i in items}
    cluster = {i.id: i.pair_id or i.id for i in items}
    res = {"models": {}, "n_items": len(items)}
    for m in sorted({r["model"] for r in rows}):
        corr, pred = defaultdict(dict), defaultdict(dict)
        unanswered = defaultdict(int)
        for r in rows:
            if r["model"] == m and r["item_id"] in by_id:
                corr[r["condition"]][r["item_id"]] = int(r["pred"] == r["gold"])
                pred[r["condition"]][r["item_id"]] = r["pred"]
                unanswered[r["condition"]] += r["pred"] is None
        out = {"accuracy": {}, "tests": {}, "sensitivity": {}, "diagnostics": {}, "depth": {}}
        gold_undet = float(np.mean([i.gold == "undetermined" for i in items]))
        for c, d in sorted(corr.items()):
            ids = list(d)
            bal, mf1 = _balanced([by_id[i].gold for i in ids], [pred[c][i] for i in ids])
            out["accuracy"][c] = {"acc": float(np.mean(list(d.values()))), "n": len(ids), "balanced": bal,
                                  "macro_f1": mf1, "unanswered": unanswered[c],
                                  "undetermined_rate": float(np.mean([pred[c][i] == "undetermined" for i in ids])),
                                  "gold_undetermined_rate": gold_undet}
            if c.startswith("N1"):  # coverage: the reasoner answered (not the prompted fallback)
                fb = [r for r in rows if r["model"] == m and r["condition"] == c and r["item_id"] in by_id]
                cov = [r for r in fb if not r.get("fallback")]
                out["accuracy"][c]["coverage"] = len(cov) / len(fb) if fb else None
                out["accuracy"][c]["acc_covered"] = (float(np.mean([r["pred"] == r["gold"] for r in cov]))
                                                     if cov else None)
            depth = defaultdict(list)
            for i, v in d.items():
                if by_id[i].depth is not None:
                    depth[by_id[i].depth].append(v)
            out["depth"][c] = {str(k): [float(np.mean(v)), len(v)] for k, v in sorted(depth.items())}

        out["tests"] = confirmatory(corr, cluster)
        if "G2" in corr and "B1" in corr:
            out["tests"]["H1u G2>B1 unseen"] = _paired(
                {i: v for i, v in corr["B1"].items() if by_id[i].split == "test_unseen"},
                {i: v for i, v in corr["G2"].items() if by_id[i].split == "test_unseen"}, cluster)
        # S1 pilot-disjoint, S2 per language
        out["sensitivity"]["S1 pilot-disjoint"] = confirmatory(
            corr, cluster, lambda i: by_id[i].meta.get("pilot_overlap") == "none")
        for lang in ("en", "es"):
            out["sensitivity"][f"S2 {lang}"] = confirmatory(corr, cluster, lambda i, lang=lang: by_id[i].lang == lang)
        # S5 balanced accuracy and macro-F1 for H1 and H2
        s5 = {}
        for b, a in [("G2", "B1"), *H2]:
            if a in pred and b in pred:
                for name, k in (("balanced", 0), ("macro_f1", 1)):
                    s5[f"{b}-{a} {name}"] = boot_metric_diff(items, pred[a], pred[b], cluster,
                                                             lambda g, p, k=k: _balanced(g, p)[k])
        out["sensitivity"]["S5"] = s5
        # section 7 diagnostics
        twin = {i.id: i for i in items}
        intact = {("abl:" + (i.pair_id or ""), i.lang): i.id for i in items if i.meta.get("block") == "deep_real"}
        for c in corr:
            p = pred[c]
            sens = []
            for it in items:
                if it.meta.get("block") == "ablation" and it.id in p:
                    t = intact.get((it.pair_id, it.lang))
                    if t in p:
                        sens.append(int(p[t] == twin[t].gold and p[it.id] == "undetermined"))

            def acc(f, c=c, corr=corr):
                v = [corr[c][i] for i in corr[c] if f(by_id[i])]
                return [float(np.mean(v)), len(v)] if v else None

            out["diagnostics"][c] = {
                "evidence_sensitivity": [float(np.mean(sens)), len(sens)] if sens else None,
                "counterfactual_affected": acc(lambda i: i.meta.get("cf_kind") == "affected"),
                "counterfactual_control": acc(lambda i: i.meta.get("cf_kind") == "control"),
                "exceptions": acc(lambda i: i.meta.get("block") == "exceptions"),
                "novel": acc(lambda i: i.meta.get("block") == "novel")}
        res["models"][m] = out
    h1 = [v["tests"].get("H1 G2>B1") for v in res["models"].values()]
    sig = sum(1 for t in h1 if t and t["p_cluster_t"] < ALPHA)
    res["H1_decision"] = {"significant_models": sig, "models": len(h1), "supported": sig >= 2}
    return res


def write_long(rows, items, path):
    """One row per model x condition x item, for the mixed model (scripts/main_glmm.R)."""
    by_id = {i.id: i for i in items}
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["model", "condition", "item_id", "pair_id", "focus_concept", "lang", "split", "depth", "block",
                    "pilot_overlap", "correct"])
        for r in rows:
            it = by_id.get(r["item_id"])
            if it is None:
                continue
            w.writerow([r["model"], r["condition"], it.id, it.pair_id or it.id,
                        (it.focus_concepts or [""])[0], it.lang, it.split, "" if it.depth is None else it.depth,
                        it.meta.get("block", ""), it.meta.get("pilot_overlap", ""), int(r["pred"] == r["gold"])])


def glmm_python(long_path):
    """Fallback for lme4 (analysis plan, section 5): variational Bayes logistic mixed model."""
    import pandas as pd
    from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM

    df = pd.read_csv(long_path)
    df = df[df.condition.isin(["B1", "G1", "G2", "G3", "G4", "R1", "N1R", "N1P2"])]
    formula = "correct ~ C(condition, Treatment('G2')) * C(model)"
    vc = {"pair": "0 + C(pair_id)", "concept": "0 + C(focus_concept)"}
    fit = BinomialBayesMixedGLM.from_formula(formula, vc, df).fit_vb()
    return fit.summary().as_text()


def render(res) -> str:
    L = ["# Main study: confirmatory analysis (docs/analysis_plan.md, tag prereg-v1)", "",
         (f"Items: {res['n_items']} (deep contrast subset, test splits). "
          f"H1 supported: **{res['H1_decision']['supported']}** "
          f"({res['H1_decision']['significant_models']} of {res['H1_decision']['models']} models)."), ""]

    def fmt_test(k, t):
        if not t:
            return None
        if "p_tost" in t:
            return (f"| {k} | {t['diff']:+.3f} | 90 % [{t['ci90'][0]:+.3f}, {t['ci90'][1]:+.3f}] | "
                    f"TOST {t['p_tost']:.4f} ({'equivalent' if t['equivalent'] else 'not shown'}) | – | "
                    f"superiority {t['p_b_greater']:.4f} |")
        p = t.get("p_two_sided", t["p_cluster_t"])
        return (f"| {k} | {t['diff']:+.3f} | [{t['ci95'][0]:+.3f}, {t['ci95'][1]:+.3f}] | {p:.4f} | "
                f"{t.get('p_holm', float('nan')):.4f} | {t['p_mcnemar_en']:.4f} |")

    for m, v in res["models"].items():
        L += [f"## {m}", "", "| Condition | acc | balanced | macro-F1 | % undet (gold) | coverage | unanswered | n |",
              "|---|---|---|---|---|---|---|---|"]
        for c, a in v["accuracy"].items():
            cov = f"{a['coverage']:.3f}" if a.get("coverage") is not None else "–"
            L.append(f"| {c} | {a['acc']:.3f} | {a['balanced']:.3f} | {a['macro_f1']:.3f} | "
                     f"{100 * a['undetermined_rate']:.0f} ({100 * a['gold_undetermined_rate']:.0f}) | {cov} | "
                     f"{a['unanswered']} | {a['n']} |")
        head = ["", "| Test | Δ | CI | p | p Holm | p McNemar EN (one-sided) |", "|---|---|---|---|---|---|"]
        L += head + [x for k, t in v["tests"].items() if (x := fmt_test(k, t))]
        for s in ("S1 pilot-disjoint", "S2 en", "S2 es"):
            L += ["", f"### {s}"] + head + [x for k, t in v["sensitivity"][s].items() if (x := fmt_test(k, t))]
        L += ["", "### S5 balanced accuracy / macro-F1", "", "| Contrast | Δ | 95 % CI |", "|---|---|---|"]
        for k, t in v["sensitivity"]["S5"].items():
            L.append(f"| {k} | {t['diff']:+.3f} | [{t['ci95'][0]:+.3f}, {t['ci95'][1]:+.3f}] |")
        L += ["", "### Diagnostics (accuracy, n)", "",
              "| Condition | evidence sensitivity | CF affected | CF control | exceptions | novel |", "|---|---|---|---|---|---|"]
        for c, d in v["diagnostics"].items():
            L.append(f"| {c} | " + " | ".join("–" if d[k] is None else f"{d[k][0]:.3f} ({d[k][1]})" for k in
                                               ("evidence_sensitivity", "counterfactual_affected",
                                                "counterfactual_control", "exceptions", "novel")) + " |")
        L.append("")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", nargs="+", required=True)
    ap.add_argument("--bench", default="data/processed/fgkb_reason_main.jsonl")
    ap.add_argument("--out", default="results/main_analysis.json")
    ap.add_argument("--report", default="docs/main_report.md")
    ap.add_argument("--long", default="results/main_long.csv", help="long table for scripts/main_glmm.R")
    ap.add_argument("--glmm-python", action="store_true", help="fit the statsmodels fallback mixed model")
    a = ap.parse_args(argv)
    items = analysis_items(a.bench)
    rows = load_rows(a.results)
    res = analyse(rows, items)
    write_long(rows, items, a.long)
    text = render(res)
    if a.glmm_python:
        res["glmm_python"] = glmm_python(a.long)
        text += "\n## Pooled logistic mixed model (statsmodels VB fallback)\n\n```\n" + res["glmm_python"] + "\n```\n"
    Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    Path(a.report).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
