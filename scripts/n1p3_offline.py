"""N1P3 from existing N1P2 runs, without the LLM (exploratory).

N1P3 uses the same parser, prompts and decoding as N1P2; it only changes the decision on queries the reasoner
cannot decide (pipeline/neurosymbolic.py, ``normalised``). So the N1P3 answer of an item is obtained exactly by
re-deciding the query N1P2 already generated for it. Fallback rows (no valid query) keep their answer.

    python scripts/n1p3_offline.py --results results/dev_v4_base.jsonl \\
        --bench data/processed/fgkb_reason_pilot_wordings.jsonl --out results/dev_v4_n1p3.jsonl
    python scripts/n1p3_offline.py --results results/main.jsonl results/main_wordings.jsonl \\
        --bench data/processed/fgkb_reason_main.jsonl data/processed/fgkb_reason_main_wordings.jsonl \\
        --out results/main_n1p3.jsonl
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from fgkb_llm.bench.schema import read_jsonl
from fgkb_llm.conditions.prompts import ABLATIONS, ContextBuilder
from fgkb_llm.kb.loaders import load_json
from fgkb_llm.pipeline.neurosymbolic import NeuroSymbolic


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", nargs="+", required=True)
    ap.add_argument("--bench", nargs="+", required=True)
    ap.add_argument("--kb", default="data/processed/fungramkb.json")
    ap.add_argument("--equivalences", default="data/extension/n1p3_equivalences.json",
                    help="'' to run without the WordNet equivalences")
    ap.add_argument("--source", default="N1P2")
    ap.add_argument("--name", default="N1P3")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    items = {}
    for b in a.bench:
        items.update({i.id: i for i in read_jsonl(b)})
    eq = json.loads(Path(a.equivalences).read_text(encoding="utf-8")) if a.equivalences else {}
    ctx = ContextBuilder(load_json(a.kb), budget_tokens=1500, modules=dict(ABLATIONS["+cognicon"]))
    ns = NeuroSymbolic(ctx, None, verify_loop=False, normalise=True, equivalences=eq)
    out, how = [], collections.Counter()
    for path in a.results:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                if r["condition"] != a.source or r["item_id"] not in items:
                    continue
                it = items[r["item_id"]]
                r2 = dict(r, condition=a.name, source_condition=a.source)
                q = (r.get("attempts") or [{}])[-1].get("query")
                if not r.get("fallback") and q:
                    eng = ns._engine_for(it)
                    pred, err = eng.validate(q)
                    if err is None:
                        ans, status, trace = eng.decide(it, pred)
                        r2.update(pred=ans, kb_status=status, trace=trace)
                        norm = [t for t in trace if t and t[0] == "normalised"]
                        r2["normalised"] = norm[0][1] if norm else None
                        if norm:
                            how[norm[0][1].split(";")[0].split(" ")[0] + " / " + norm[0][1].split("; ")[1].split(" ")[0]] += 1
                out.append(r2)
    Path(a.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8")
    changed = sum(1 for r in out if r.get("normalised"))
    print(f"{len(out)} rows -> {a.out}; normalised: {changed}")
    for k, v in how.most_common():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
