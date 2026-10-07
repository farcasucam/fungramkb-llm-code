"""Turn results JSONL into the paper's tables (LaTeX, booktabs) and figures.

Outputs go to ``paper/tables`` and ``paper/figures`` so Overleaf (synced with the
GitHub repo) picks them up directly.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..eval.metrics import (
    accuracy,
    by,
    contradiction_rate,
    coverage,
    depth_curve,
    evidence_following,
)
from ..eval.stats import bootstrap_ci, holm, mcnemar_exact, paired_vectors

ORDER = ["B0", "B1", "R1", "R2", "G1", "G2", "G3", "G4", "F1", "F2", "N1", "N2"]
TASKS = ["grounding", "entailment", "multihop", "procedural", "consistency"]


def load(paths) -> list[dict]:
    rows = []
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            rows += [json.loads(line) for line in fh if line.strip()]
    return rows


def main_table(rows, out: Path) -> str:
    """Accuracy per model x condition x task, with 95% bootstrap CI on the overall mean."""
    lines = [r"\begin{tabular}{ll" + "r" * (len(TASKS) + 1) + "}", r"\toprule",
             "Model & Cond. & " + " & ".join(t.capitalize() for t in TASKS) + r" & Overall \\", r"\midrule"]
    for model, mrows in sorted(by(rows, "model").items()):
        for cond in [c for c in ORDER if c in {r["condition"] for r in mrows}]:
            crows = [r for r in mrows if r["condition"] == cond]
            cells = []
            for t in TASKS:
                tr = [r for r in crows if r["task"] == t]
                cells.append(f"{100 * accuracy(tr):.1f}" if tr else "--")
            m, lo, hi = bootstrap_ci([r["pred"] == r["gold"] for r in crows])
            cells.append(f"{100 * m:.1f} \\scriptsize[{100 * lo:.1f}, {100 * hi:.1f}]")
            lines.append(f"{model} & {cond} & " + " & ".join(cells) + r" \\")
        lines.append(r"\midrule")
    lines[-1] = r"\bottomrule"
    lines.append(r"\end{tabular}")
    tex = "\n".join(lines)
    out.write_text(tex, encoding="utf-8")
    return tex


def significance(rows, baseline: str = "G1", out: Path | None = None) -> dict:
    """McNemar of every condition against a baseline, per model, Holm-corrected."""
    res = {}
    for model, mrows in by(rows, "model").items():
        base = [r for r in mrows if r["condition"] == baseline]
        pvals, stats = {}, {}
        for cond in {r["condition"] for r in mrows} - {baseline}:
            a, b = paired_vectors(base, [r for r in mrows if r["condition"] == cond])
            b01, b10, p = mcnemar_exact(a, b)
            pvals[cond], stats[cond] = p, (b01, b10)
        adj = holm(pvals)
        res[model] = {c: {"b01": stats[c][0], "b10": stats[c][1], "p": pvals[c], "p_holm": adj[c][0],
                          "significant": adj[c][1]} for c in pvals}
    if out:
        out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    return res


def depth_figure(rows, out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(5.5, 3.4))
    for cond in [c for c in ORDER if c in {r["condition"] for r in rows}]:
        curve = depth_curve([r for r in rows if r["condition"] == cond])
        if curve:
            ax.plot(list(curve), [100 * v for v in curve.values()], marker="o", label=cond)
    ax.set_xlabel("Inference depth (IS-A hops)")
    ax.set_ylabel("Accuracy (%)")
    ax.legend(ncol=3, fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(out)


def extra_metrics(rows) -> dict:
    out = {}
    for (model, cond), g in by(rows, lambda r: (r["model"], r["condition"])).items():
        out[f"{model}|{cond}"] = {
            "contradiction_rate": contradiction_rate(g),
            "evidence_following": evidence_following(g),
            "seen": accuracy(r for r in g if r["split"] == "test_seen"),
            "unseen": accuracy(r for r in g if r["split"] == "test_unseen"),
            "coverage": coverage(g) if cond in ("N1", "N2") else None,
        }
    return out


def build_all(result_files, paper_dir: str = "paper") -> None:
    rows = load(result_files)
    pd = Path(paper_dir)
    (pd / "tables").mkdir(parents=True, exist_ok=True)
    (pd / "figures").mkdir(parents=True, exist_ok=True)
    main_table(rows, pd / "tables" / "main_results.tex")
    significance(rows, out=pd / "tables" / "significance.json")
    (pd / "tables" / "extra_metrics.json").write_text(json.dumps(extra_metrics(rows), indent=2), encoding="utf-8")
    try:
        depth_figure(rows, pd / "figures" / "depth_curve.pdf")
    except ImportError:
        print("matplotlib not installed: skipping figure")
