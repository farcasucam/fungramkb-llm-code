"""Metrics for the paper (section 13 of the project script).

All functions take a list of result records (dicts) as written by ``runner.run``:
    {"item_id", "task", "lang", "split", "depth", "distractor", "pair_id",
     "gold", "pred", "condition", "model", "trace_ok", "fallback", "ctx_tokens", ...}
"""

from __future__ import annotations

from collections import defaultdict

from sklearn.metrics import f1_score


def accuracy(rows) -> float:
    rows = list(rows)
    return sum(r["pred"] == r["gold"] for r in rows) / len(rows) if rows else float("nan")


def macro_f1(rows) -> float:
    rows = list(rows)
    if not rows:
        return float("nan")
    return f1_score([r["gold"] for r in rows], [r["pred"] or "NONE" for r in rows], average="macro")


def by(rows, key) -> dict:
    out = defaultdict(list)
    for r in rows:
        out[r[key] if not callable(key) else key(r)].append(r)
    return dict(out)


def depth_curve(rows, task: str = "multihop") -> dict[int, float]:
    groups = by([r for r in rows if r["task"] == task and r.get("depth") is not None], "depth")
    return {d: accuracy(g) for d, g in sorted(groups.items())}


def contradiction_rate(rows) -> float:
    """Share of item pairs (same pair_id, e.g. EN/ES twins) whose answers are not
    mutually coherent: twins must agree."""
    pairs = by([r for r in rows if r.get("pair_id")], "pair_id")
    checked = bad = 0
    for g in pairs.values():
        by_lang = {r["lang"]: r for r in g}
        if len(by_lang) == 2:
            a, b = by_lang.values()
            checked += 1
            bad += a["pred"] != b["pred"]
    return bad / checked if checked else float("nan")


def evidence_following(rows) -> float:
    """Accuracy on distractor items, i.e. where the KB overrides a likely prior."""
    return accuracy(r for r in rows if r.get("distractor"))


def trace_verifiability(rows) -> float:
    rows = [r for r in rows if r["condition"] in ("N1", "N2") and not r.get("fallback")]
    return sum(bool(r.get("trace_ok")) for r in rows) / len(rows) if rows else float("nan")


def coverage(rows) -> float:
    rows = [r for r in rows if r["condition"] in ("N1", "N2")]
    return sum(not r.get("fallback") for r in rows) / len(rows) if rows else float("nan")


def unparsable_rate(rows) -> float:
    rows = list(rows)
    return sum(r["pred"] is None for r in rows) / len(rows) if rows else float("nan")


def summary(rows) -> dict:
    return {
        "n": len(rows),
        "accuracy": accuracy(rows),
        "macro_f1": macro_f1(rows),
        "contradiction_rate": contradiction_rate(rows),
        "evidence_following": evidence_following(rows),
        "unparsable": unparsable_rate(rows),
        "avg_ctx_tokens": sum(r.get("ctx_tokens", 0) for r in rows) / len(rows) if rows else 0,
    }
