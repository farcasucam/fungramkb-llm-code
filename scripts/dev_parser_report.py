"""Dev-split comparison of the neuro-symbolic parsers (N1, N1R, N1P) against G2.

Reads one or more result files (the pilot file has N1/N1R/G2, the dev run has N1P), keeps the dev
split of the deep contrast subset and reports, per model and condition: accuracy, macro-F1,
% undetermined, reasoner coverage (share of items with a true/false verdict), accuracy when the
reasoner decides, slot accuracy of the query (subject, event, object against the item's gold
property) and the hybrid "parser verdict, else G2". Used only to tune the parser; test splits are
not looked at until the parser is frozen.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys

from fgkb_llm.bench.contrast import contrast_subset
from fgkb_llm.bench.schema import read_jsonl
from fgkb_llm.corel.parser import try_parse

LABELS = ("yes", "no", "undetermined")
NS = ("N1", "N1R", "N1P", "N1P2")


def macro_f1(preds, golds):
    f = []
    for lab in LABELS:
        tp = sum(p == g == lab for p, g in zip(preds, golds))
        fp = sum(p == lab != g for p, g in zip(preds, golds))
        fn = sum(g == lab != p for p, g in zip(preds, golds))
        f.append(2 * tp / max(1, 2 * tp + fp + fn))
    return sum(f) / len(f)


def slots(raw):
    mp, err = try_parse("+" + (raw or ""))
    if err:
        return None
    p = mp.items[0].predications[0]
    subj = [x for x in p.participants if x.var == "x1" and x.filler_concepts()]
    obj = [x for x in p.participants if x.var != "x1" and x.filler_concepts()]
    return (subj[0].filler_concepts()[0] if subj else None, p.event, obj[0].filler_concepts()[0] if obj else "")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+")
    ap.add_argument("--bench", default="data/processed/fgkb_reason.jsonl")
    ap.add_argument("--split", default="dev")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    items = {i.id: i for i in contrast_subset([i for i in read_jsonl(a.bench) if i.task == "deep"])
             if i.split == a.split}
    rows = {}
    for path in a.results:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                if r["item_id"] in items and r["condition"] in NS + ("G2",):
                    rows[(r["model"], r["condition"], r["item_id"])] = r
    models = sorted({k[0] for k in rows})
    report = {}
    lines = [f"# Parser comparison on the {a.split} split ({len(items)} items)", "",
             ("| Model | Cond | acc | macro-F1 | % undet. | coverage | acc when decided | subject | event | object "
              "| hybrid acc | hybrid F1 |"), "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m in models:
        for cond in NS + ("G2",):
            ids = [i for i in items if (m, cond, i) in rows]
            if not ids:
                continue
            rs = [rows[(m, cond, i)] for i in ids]
            golds = [items[i].gold for i in ids]
            preds = [r["pred"] for r in rs]
            c = collections.Counter()
            hyb = []
            for i, r in zip(ids, rs):
                it = items[i]
                decided = r.get("kb_status") in ("true", "false")
                c["decided"] += decided
                c["decided_ok"] += decided and r["pred"] == it.gold
                g2 = rows.get((m, "G2", i))
                hyb.append(r["pred"] if decided or g2 is None else g2["pred"])
                if cond != "G2":
                    sl = None if r.get("fallback") else slots(r.get("raw"))
                    ev, _, _, fill = it.meta["prop"]
                    if sl:
                        c["subject"] += sl[0] == it.focus_concepts[0]
                        c["event"] += sl[1] == ev
                        c["object"] += sl[2] == fill
            n = len(ids)
            rec = {"n": n, "acc": sum(p == g for p, g in zip(preds, golds)) / n, "macro_f1": macro_f1(preds, golds),
                   "undetermined": sum(p == "undetermined" for p in preds) / n}
            if cond != "G2":
                rec.update({"coverage": c["decided"] / n, "acc_decided": c["decided_ok"] / max(1, c["decided"]),
                            "subject": c["subject"] / n, "event": c["event"] / n, "object": c["object"] / n,
                            "hybrid_acc": sum(p == g for p, g in zip(hyb, golds)) / n,
                            "hybrid_f1": macro_f1(hyb, golds)})
            report[f"{m}/{cond}"] = rec

            def f(k, rec=rec):
                return f"{rec[k]:.3f}" if k in rec else "–"

            lines.append(f"| {m} | {cond} | {f('acc')} | {f('macro_f1')} | {f('undetermined')} | {f('coverage')} | "
                         f"{f('acc_decided')} | {f('subject')} | {f('event')} | {f('object')} | {f('hybrid_acc')} | "
                         f"{f('hybrid_f1')} |")
    text = "\n".join(lines)
    print(text)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return report


if __name__ == "__main__":
    sys.exit(0 if main() is not None else 1)
