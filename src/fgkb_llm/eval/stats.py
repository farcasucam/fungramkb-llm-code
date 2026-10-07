"""Statistical protocol: bootstrap CIs, exact McNemar, Holm-Bonferroni."""

from __future__ import annotations

import numpy as np
from scipy.stats import binomtest


def bootstrap_ci(correct: list[bool] | np.ndarray, n_boot: int = 10_000, alpha: float = 0.05,
                 seed: int = 0) -> tuple[float, float, float]:
    x = np.asarray(correct, dtype=float)
    if len(x) == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), size=(n_boot, len(x)))
    means = x[idx].mean(axis=1)
    return float(x.mean()), float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def mcnemar_exact(a_correct, b_correct) -> tuple[int, int, float]:
    """Paired comparison on the same items. Returns (b01, b10, p-value)."""
    a = np.asarray(a_correct, dtype=bool)
    b = np.asarray(b_correct, dtype=bool)
    b01 = int(np.sum(~a & b))
    b10 = int(np.sum(a & ~b))
    n = b01 + b10
    p = 1.0 if n == 0 else binomtest(b01, n, 0.5).pvalue
    return b01, b10, float(p)


def holm(pvalues: dict[str, float], alpha: float = 0.05) -> dict[str, tuple[float, bool]]:
    """Holm-Bonferroni step-down. Returns adjusted p and reject flag per key."""
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(items)
    out, running = {}, 0.0
    for i, (k, p) in enumerate(items):
        adj = min(1.0, (m - i) * p)
        running = max(running, adj)
        out[k] = (running, running <= alpha)
    return out


def paired_vectors(rows_a, rows_b) -> tuple[list[bool], list[bool]]:
    """Align two conditions on item_id."""
    a = {r["item_id"]: r["pred"] == r["gold"] for r in rows_a}
    b = {r["item_id"]: r["pred"] == r["gold"] for r in rows_b}
    common = sorted(set(a) & set(b))
    return [a[i] for i in common], [b[i] for i in common]
