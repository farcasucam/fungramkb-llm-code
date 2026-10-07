"""N1P checks without an LLM (run on the dev split while tuning the parser, then on all splits once).

1. Candidate coverage: is the gold subject / event / object among the slot candidates?
2. Oracle: feed the gold slots (as a perfect model would) through query building, validation and the
   role-tolerant decision; accuracy must stay close to 100 % (the N1P analogue of V7).
"""

from __future__ import annotations

import argparse
import collections
import json

from fgkb_llm.bench.contrast import contrast_subset
from fgkb_llm.bench.schema import read_jsonl
from fgkb_llm.conditions.prompts import ContextBuilder
from fgkb_llm.kb.loaders import load_json
from fgkb_llm.pipeline.neurosymbolic import NeuroSymbolic


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", default="data/processed/fungramkb.json")
    ap.add_argument("--bench", default="data/processed/fgkb_reason.jsonl")
    ap.add_argument("--split", default="dev", help="dev | test_seen | test_unseen | all")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    ctx = ContextBuilder(load_json(a.kb), budget_tokens=1500)
    items = contrast_subset([i for i in read_jsonl(a.bench) if i.task == "deep"])
    if a.split != "all":
        items = [i for i in items if i.split == a.split]
    ns = NeuroSymbolic(ctx, backend=None, verify_loop=False, pinned=True)
    c = collections.Counter()
    misses = []
    for it in items:
        eng = ns._engine_for(it)
        sl = eng.slots(it)
        ev, _, _, fill = it.meta["prop"]
        subj = it.focus_concepts[0]
        c["n"] += 1
        c["subject_in"] += subj in sl["subjects"]
        c["subject_first"] += bool(sl["subjects"]) and sl["subjects"][0] == subj
        c["event_in"] += ev in sl["events"]
        c["event_cued"] += ev in sl["cue_events"]
        c["object_in"] += (not fill) or fill in sl["objects"]
        q = eng.slots_to_query({"negated": False, "subject": subj, "event": ev, "object": fill})
        pred, err = eng.validate(q)
        if err:
            c["oracle_invalid"] += 1
            misses.append((it.id, q, err))
            continue
        answer, status, _ = eng.decide(it, pred)
        c["oracle_correct"] += answer == it.gold
        if answer != it.gold and len(misses) < 30:
            misses.append((it.id, q, f"oracle {answer} vs gold {it.gold} ({status})"))
    n = c["n"] or 1
    report = {k: (v if k == "n" else round(v / n, 3)) for k, v in c.items()}
    print(json.dumps(report, indent=1))
    for m in misses[:30]:
        print(*m, sep="  |  ")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump({"split": a.split, "report": report, "misses": misses}, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
