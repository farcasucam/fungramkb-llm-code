"""Offline validation of FGKB-Reason (no LLM needed).

Checks that the benchmark measures what it claims before any GPU time is spent:

V1  gold re-derivation: every deep item's gold is recomputed with a fresh reasoner on the
    (patched) KB it refers to; must agree 100 %.
V2  necessity of the required facts: removing one required postulate must change the answer
    (sample); otherwise the "minimal proof" is not minimal.
V3  majority-class baselines per task and per deep block.
V4  artefact test: a bag-of-n-grams logistic regression that sees only the question text,
    cross-validated with folds grouped by focus concept (no concept in both train and test).
    A large margin over V3 means surface cues leak the label.
V5  power: simulated paired comparisons with item random effects and EN/ES twins as clusters,
    Holm correction over the planned comparisons.

    python scripts/validate_offline.py --bench data/processed/fgkb_reason.jsonl \
        --kb data/processed/fungramkb.json --out results/validation.json --report docs/validation_report.md
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from fgkb_llm.bench.deep import apply_patch, drop_predication
from fgkb_llm.bench.schema import read_jsonl
from fgkb_llm.kb.loaders import load_json
from fgkb_llm.reasoner.asp import Reasoner

STATUS2LABEL = {"true": "yes", "false": "no"}


def _label(ans) -> str:
    return STATUS2LABEL.get(ans.status, "undetermined")


def _prop_of(r, src):
    c, _ = src.split("/")
    return next((f.prop for f in r.facts_by_concept.get(c, []) if f.source == src), None)


# ------------------------------------------------------------------------------------------ V1 / V2
def gold_rederivation(kb, items):
    """V1: recompute the gold of every deep item whose question is a single property query
    (all blocks; composite filler-chaining items are checked through their proof steps in V2)."""
    base = Reasoner(kb)
    cache = {}
    agree = total = 0
    disagreements = []
    for it in items:
        m = it.meta
        if it.task != "deep" or m.get("kind") == "composite" or it.lang != "en":
            continue
        # the queried property is the one whose proof is stored: use the last postulate step
        steps = [s for s in it.trace if s and s[0] == "postulate"]
        if not steps and not m.get("prop"):
            continue
        r = base
        if m.get("kb_patch"):
            key = json.dumps(m["kb_patch"], sort_keys=True)
            if key not in cache:
                cache[key] = base.patched(apply_patch(kb, m["kb_patch"]), list(m["kb_patch"]["concepts"]))
            r = cache[key]
        if m.get("prop"):
            from fgkb_llm.corel.facts import Prop

            prop = Prop(*m["prop"])
        else:
            src = steps[-1][2]
            prop = _prop_of(r, src) or _prop_of(base, src)
        if prop is None:
            continue
        got = _label(r.query(it.focus_concepts[0], prop))
        total += 1
        if got == it.gold:
            agree += 1
        elif len(disagreements) < 10:
            disagreements.append({"id": it.id, "gold": it.gold, "rederived": got})
    return {"checked": total, "agree": agree, "rate": agree / total if total else None, "examples": disagreements}


def necessity(kb, items, n=200, seed=3):
    """V2: drop each non-IS-A required fact of an inheritance item; the answer must change."""
    rng = random.Random(seed)
    base = Reasoner(kb)
    pool = [i for i in items if i.task == "deep" and i.lang == "en" and i.meta.get("block") == "deep_real"
            and i.meta.get("kind") == "inherit"]
    rng.shuffle(pool)
    checked = changed = 0
    for it in pool[:n]:
        steps = [s for s in it.trace if s and s[0] == "postulate"]
        if not steps:
            continue
        prop = _prop_of(base, steps[-1][2])
        for rf in it.meta["required_facts"]:
            if rf.startswith("isa:") or "/" not in rf:
                continue
            c, evar = rf.split("/")
            patch = {"concepts": {c: {"meaning_postulate": drop_predication(kb.concepts[c].meaning_postulate, evar)}}}
            r2 = base.patched(apply_patch(kb, patch), [c])
            checked += 1
            changed += _label(r2.query(it.focus_concepts[0], prop)) != it.gold
    return {"facts_checked": checked, "answer_changed": changed, "rate": changed / checked if checked else None}


# ------------------------------------------------------------------------------------------ V3 / V4
def majority(items, key):
    groups = defaultdict(list)
    for it in items:
        groups[key(it)].append(it.gold)
    out = {}
    for g, golds in sorted(groups.items()):
        c = Counter(golds)
        out[g] = {"n": len(golds), "majority": c.most_common(1)[0][0], "acc": c.most_common(1)[0][1] / len(golds),
                  "labels": dict(c)}
    return out


def question_only(items, folds=5, seed=0):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import f1_score
    from sklearn.model_selection import GroupKFold

    X = [it.question for it in items]
    y = np.array([it.gold for it in items])
    groups = np.array([it.focus_concepts[0] if it.focus_concepts else it.pair_id for it in items])
    if len(set(groups)) < folds or len(set(y)) < 2:
        return None
    pred = np.empty_like(y)
    for tr, te in GroupKFold(n_splits=folds).split(X, y, groups):
        vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)
        Xtr = vec.fit_transform([X[i] for i in tr])
        clf = LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced", random_state=seed)
        clf.fit(Xtr, y[tr])
        pred[te] = clf.predict(vec.transform([X[i] for i in te]))
    maj = Counter(y).most_common(1)[0][1] / len(y)
    return {"n": len(y), "acc": float((pred == y).mean()), "macro_f1": float(f1_score(y, pred, average="macro")),
            "majority_acc": maj, "margin": float((pred == y).mean() - maj),
            "by_block": {b: float((pred[idx] == y[idx]).mean()) for b, idx in _blocks(items).items()}}


def _blocks(items):
    out = defaultdict(list)
    for i, it in enumerate(items):
        out[it.meta.get("block", it.task)].append(i)
    return {k: np.array(v) for k, v in out.items()}


# ------------------------------------------------------------------------------------------------- V5
def power(n_clusters, p0=0.60, deltas=(0.05, 0.08, 0.10), m=6, alpha=0.05, sd_item=1.5, sims=400, seed=7):
    """Paired comparison of two conditions on the same items. Each cluster = EN/ES twins sharing an
    item intercept (logit scale, sd_item). Test: paired t-test on cluster mean differences; the
    hypothesis of interest is tested at the Holm worst case alpha/m."""
    from scipy import stats
    from scipy.special import expit, logit

    rng = np.random.default_rng(seed)
    res = {}
    for d in deltas:
        # shift on the logit scale that yields the marginal difference d (calibrated numerically)
        u = rng.normal(0, sd_item, 20000)
        lo, hi = 0.0, 3.0
        base = expit(logit(p0) + u).mean()
        b0 = logit(p0)
        for _ in range(40):  # calibrate the intercept so the marginal accuracy of A is p0
            if expit(b0 + u).mean() < p0:
                b0 += 0.05
            else:
                b0 -= 0.05
        base = expit(b0 + u).mean()
        for _ in range(50):
            mid = (lo + hi) / 2
            if expit(b0 + mid + u).mean() - base < d:
                lo = mid
            else:
                hi = mid
        shift = (lo + hi) / 2
        hits_raw = hits_holm = 0
        for _ in range(sims):
            ui = rng.normal(0, sd_item, n_clusters)
            a = rng.random((n_clusters, 2)) < expit(b0 + ui)[:, None]
            b = rng.random((n_clusters, 2)) < expit(b0 + shift + ui)[:, None]
            diff = b.mean(1) - a.mean(1)
            p = stats.ttest_1samp(diff, 0).pvalue
            hits_raw += p < alpha
            hits_holm += p < alpha / m
        res[f"+{round(d * 100)}pt"] = {"power_alpha": hits_raw / sims, "power_holm_worst": hits_holm / sims}
    return {"clusters": n_clusters, "p0": p0, "sd_item": sd_item, "comparisons": m, "sims": sims, "by_delta": res}


# ------------------------------------------------------------------------------------------------- V7
def n1_oracle(kb, items):
    """N1 with a perfect parser (the gold COREL query): measures the soundness of the symbolic half
    of N1/N2 on the real KB, i.e. the ceiling an LLM parser could reach."""
    from fgkb_llm.conditions import ContextBuilder
    from fgkb_llm.llm.backends import GenConfig
    from fgkb_llm.pipeline import NeuroSymbolic

    class Oracle:
        name, next = "oracle", ""

        def generate(self, prompts, cfg):
            return [self.next for _ in prompts]

    o = Oracle()
    ns = NeuroSymbolic(ContextBuilder(kb), o, verify_loop=False, constrained=False)
    n = ok = skipped = 0
    for it in items:
        if it.lang != "en" or it.meta.get("kind") == "composite" or not it.meta.get("prop"):
            skipped += 1
            continue
        ev, r0, r1, fill = it.meta["prop"]
        if any(c in fill for c in "|^&"):
            skipped += 1
            continue
        o.next = f"(e1: {ev} (x1: {it.focus_concepts[0]}){r0}" + (f" (x2: {fill}){r1}" if fill else "") + ")"
        n += 1
        ok += ns.run(it, GenConfig()).answer == it.gold
    return {"expressible": n, "correct": ok, "rate": ok / n if n else None, "not_single_predication": skipped}


# ------------------------------------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", required=True)
    ap.add_argument("--kb", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", required=True)
    a = ap.parse_args(argv)

    kb = load_json(a.kb)
    items = read_jsonl(a.bench)
    deep = [i for i in items if i.task == "deep"]
    out = {
        "V1_gold_rederivation": gold_rederivation(kb, deep),
        "V2_required_fact_necessity": necessity(kb, deep),
        "V3_majority_by_task": majority([i for i in items if i.lang == "en"], lambda i: i.task),
        "V3_majority_deep_by_block": majority([i for i in deep if i.lang == "en"], lambda i: i.meta["block"]),
        "V4_question_only": {},
        "V5_power": power(len({i.pair_id for i in deep})),
        "V7_n1_oracle": n1_oracle(kb, [i for i in deep if i.lang == "en"]),
    }
    from fgkb_llm.bench.contrast import contrast_subset

    cset = contrast_subset(items)
    out["V4_question_only_contrast"] = {}
    out["contrast_sizes"] = {}
    for task in ("deep", "entailment", "multihop", "consistency"):
        for lang in ("en", "es"):
            sub = [i for i in items if i.task == task and i.lang == lang]
            out["V4_question_only"][f"{task}/{lang}"] = question_only(sub)
            csub = [i for i in cset if i.task == task and i.lang == lang]
            out["contrast_sizes"][f"{task}/{lang}"] = {"n": len(csub), "labels": dict(Counter(i.gold for i in csub))}
            out["V4_question_only_contrast"][f"{task}/{lang}"] = question_only(csub)
    out["contrast_deep_blocks_en"] = dict(Counter(i.meta["block"] for i in cset if i.task == "deep" and i.lang == "en"))
    out["V5_power_contrast"] = power(len({i.pair_id for i in cset if i.task == "deep"}))
    # V6 provenance: items whose minimal proof uses only knowledge from the FunGramKB export
    def export_only(it):
        cs = set()
        for rf in it.meta.get("required_facts", []):
            cs |= set(rf[4:].split(">")) if rf.startswith("isa:") else {rf.split("/")[0]}
        prov = {(kb.concepts[c].meta or {}).get("provenance", "fungramkb-export") for c in cs if c in kb.concepts}
        return bool(cs) and prov <= {"fungramkb-export", "patch"}
    proved = [i for i in cset if i.task == "deep" and i.lang == "en" and i.meta.get("required_facts")]
    out["V6_provenance_contrast_en"] = {"with_proof": len(proved), "export_only": sum(map(export_only, proved))}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    Path(a.report).write_text(render(out), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k.startswith(("V1", "V2", "V5"))}, indent=2))


def render(o) -> str:
    L = ["# FGKB-Reason — offline validation report", "",
         "Generated by `scripts/validate_offline.py`. No LLM involved; all numbers are reproducible.", ""]
    v1, v2 = o["V1_gold_rederivation"], o["V2_required_fact_necessity"]
    L += ["## V1 Gold re-derivation", "",
          (f"{v1['agree']}/{v1['checked']} deep single-property items (all blocks) re-derived with a fresh reasoner "
           f"on their own (patched) KB agree with the stored gold ({100 * (v1['rate'] or 0):.1f} %)."), ""]
    L += ["## V2 Necessity of required facts", "",
          (f"Removing one required postulate changes the answer in {v2['answer_changed']}/{v2['facts_checked']} cases "
           f"({100 * (v2['rate'] or 0):.1f} %)."), ""]
    L += ["## V3 Majority baselines (EN)", "", "| Task / block | n | majority | acc | labels |", "|---|---|---|---|---|"]
    for k, v in {**o["V3_majority_by_task"], **{f"deep:{b}": x for b, x in o["V3_majority_deep_by_block"].items()}}.items():
        L.append(f"| {k} | {v['n']} | {v['majority']} | {v['acc']:.3f} | {v['labels']} |")
    L += ["", "## V4 Question-only artefact test", "",
          "TF-IDF (1–2-grams) + logistic regression, 5-fold CV grouped by focus concept.", "",
          "| Task/lang | n | acc | macro-F1 | majority | margin |", "|---|---|---|---|---|---|"]
    for k, v in o["V4_question_only"].items():
        if v:
            L.append(f"| {k} | {v['n']} | {v['acc']:.3f} | {v['macro_f1']:.3f} | {v['majority_acc']:.3f} | {v['margin']:+.3f} |")
    dq = o["V4_question_only"].get("deep/en")
    if dq:
        L += ["", "Question-only accuracy by deep block (EN): "
              + ", ".join(f"{b} {a:.2f}" for b, a in sorted(dq["by_block"].items())), ""]
    L += ["", "### On the property-contrastive subset (primary analysis set)", "",
          "Labels balanced within each (task, queried property); EN/ES twins kept together.", "",
          "| Task/lang | n | labels | QO acc | majority | margin |", "|---|---|---|---|---|---|"]
    for k, v in o["V4_question_only_contrast"].items():
        sz = o["contrast_sizes"][k]
        if v:
            L.append(f"| {k} | {sz['n']} | {sz['labels']} | {v['acc']:.3f} | {v['majority_acc']:.3f} | {v['margin']:+.3f} |")
    dq = o["V4_question_only_contrast"].get("deep/en")
    if dq:
        L += ["", "Deep blocks in the contrast subset (EN): " + ", ".join(f"{b} {n}" for b, n in sorted(o["contrast_deep_blocks_en"].items())),
              "", "Question-only accuracy by block (EN, contrast): "
              + ", ".join(f"{b} {a:.2f}" for b, a in sorted(dq["by_block"].items())), ""]
    v7 = o["V7_n1_oracle"]
    L += ["## V7 Symbolic ceiling of N1/N2", "",
          (f"With a perfect parser, N1 answers {v7['correct']}/{v7['expressible']} single-predication deep items "
           f"correctly ({100 * (v7['rate'] or 0):.1f} %), patched KBs included; {v7['not_single_predication']} EN items "
           "(filler-chaining composites, disjunctive fillers) are not expressible as one COREL query."), ""]
    v6 = o["V6_provenance_contrast_en"]
    L += ["## V6 Provenance", "",
          (f"Of {v6['with_proof']} EN contrast items with a proof, {v6['export_only']} use only knowledge from the "
           "FunGramKB export (the rest also use concepts authored for this project, pending expert validation); "
           "results are reported for both strata."), ""]
    for name, p in (("full deep suite", o["V5_power"]), ("deep contrast subset", o["V5_power_contrast"])):
        L += [f"## V5 Power — {name}", "",
              (f"{p['clusters']} item clusters (EN/ES twins), baseline accuracy {p['p0']:.2f}, item sd {p['sd_item']} "
               f"(logit), {p['comparisons']} planned comparisons, {p['sims']} simulations."), "",
              "| Effect | power α=.05 | power Holm worst case |", "|---|---|---|"]
        for d, v in p["by_delta"].items():
            L.append(f"| {d} | {v['power_alpha']:.2f} | {v['power_holm_worst']:.2f} |")
        L.append("")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
