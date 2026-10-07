"""KB audit report: what the experiments actually run on (docs/kb_report.md).

    python scripts/kb_report.py --kb data/processed/fungramkb.json --bench data/processed/fgkb_reason.jsonl \
        --out docs/kb_report.md --nlg-sample docs/nlg_audit_sample.tsv
"""

from __future__ import annotations

import argparse
import csv
import random
from collections import Counter
from pathlib import Path

from fgkb_llm.bench.schema import read_jsonl
from fgkb_llm.kb.loaders import load_json
from fgkb_llm.reasoner.asp import Reasoner


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", required=True)
    ap.add_argument("--bench")
    ap.add_argument("--out", required=True)
    ap.add_argument("--nlg-sample", help="TSV of stratified items for expert rating of fluency/faithfulness")
    ap.add_argument("--per-block", type=int, default=10)
    a = ap.parse_args(argv)

    kb = load_json(a.kb)
    r = Reasoner(kb)
    prov = Counter((c.meta or {}).get("provenance", "fungramkb-export") for c in kb.concepts.values())
    types = Counter(c.semantic_type for c in kb.concepts.values() if not c.id.startswith("#"))
    with_mp = [c for c in kb.with_postulates()]
    mp_prov = Counter((c.meta or {}).get("provenance", "fungramkb-export") for c in with_mp)
    lex = Counter(lu.lang for lu in kb.lexicon)
    import json

    raw_lex = json.loads(Path(a.kb).read_text(encoding="utf-8"))["lexicon"]
    repaired = sum(1 for lu in raw_lex if lu.get("lemma_repaired_from"))
    corrupt = sum(1 for lu in kb.lexicon if getattr(lu, "corrupt", False))
    depth = Counter()
    for c in kb.concepts:
        if not c.startswith("#"):
            depth[len([x for x in kb.ancestors(c) if not x.startswith("#")])] += 1
    fact_prov = Counter((kb.concepts[f.concept].meta or {}).get("provenance", "fungramkb-export") for f in r.facts)

    L = ["# KB audit report", "", f"KB version: `{kb.version}`", "",
         "## Concepts", "", "| Provenance | concepts | with meaning postulate | facts extracted |", "|---|---|---|---|"]
    for p, n in prov.most_common():
        L.append(f"| {p} | {n} | {mp_prov.get(p, 0)} | {fact_prov.get(p, 0)} |")
    L += ["", "Semantic types (non-meta): " + ", ".join(f"{t} {n}" for t, n in types.most_common()), "",
          "Taxonomic depth below the metaconcept layer: " + ", ".join(f"{d}: {n}" for d, n in sorted(depth.items())), "",
          "## Meaning postulates", "",
          (f"{len(with_mp)} postulates; {len(with_mp) - len(r.parse_errors)} parse "
           f"({100 * (1 - len(r.parse_errors) / max(1, len(with_mp))):.1f} %); {len(r.facts)} property facts, "
           f"{len(r.mp_isas)} IS-A links read from BE_00 classifications."), ""]
    if r.parse_errors:
        L += ["Parse errors (to be fixed in the KB, reported to the FunGramKB team):", ""]
        L += [f"- `{cid}`: {msg[:160]}" for cid, msg in sorted(r.parse_errors.items())]
        L.append("")
    L += ["## Lexicon", "", "Lexical units by language: " + ", ".join(f"{k} {v}" for k, v in lex.most_common())
          + f"; Spanish lemmas with accents restored from the Latin-1 export: {repaired}; unrecoverable (excluded): {corrupt}.", "",
          f"## Cognicon\n\n{len(kb.scripts)} scripts, {sum(len(s.steps) for s in kb.scripts.values())} steps.", ""]
    if a.bench:
        items = read_jsonl(a.bench)
        by = Counter((i.task, i.meta.get("block", "")) for i in items if i.lang == "en")
        L += ["## Benchmark (EN; ES twins identical in number)", "", "| Task | block | items |", "|---|---|---|"]
        L += [f"| {t} | {b} | {n} |" for (t, b), n in sorted(by.items())]
        L.append("")
        if a.nlg_sample:
            rng = random.Random(5)
            rows = []
            blocks = sorted({i.meta.get("block", i.task) for i in items})
            for b in blocks:
                pool = [i for i in items if i.lang == "en" and i.meta.get("block", i.task) == b]
                rng.shuffle(pool)
                for it in pool[: a.per_block]:
                    es = next((j for j in items if j.pair_id == it.pair_id and j.lang == "es"), None)
                    rows.append([it.id, b, it.gold, it.question, es.question if es else "", "", "", ""])
            with open(a.nlg_sample, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh, delimiter="\t")
                w.writerow(["id", "block", "gold", "question_en", "question_es",
                            "fluency_en_1to5", "fluency_es_1to5", "faithful_to_KB_yes_no"])
                w.writerows(rows)
            L += [f"An expert-rating sample of {len(rows)} items (stratified by block) is in `{a.nlg_sample}`.", ""]
    Path(a.out).write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L[:30]))


if __name__ == "__main__":
    main()
