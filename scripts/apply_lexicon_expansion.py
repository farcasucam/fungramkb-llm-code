"""Add expert-approved lexical units (docs/lexicon_candidates.tsv, column "approve (1/0)") to the KB.

The new units are appended after the existing ones, so the first lemma of every concept (used by the
verbaliser to write questions and contexts) does not change; they only widen what the shared linker and
N1P's event cue recognise. They carry ``provenance = lexicon-expansion-<date>`` so the paper can report the
expansion separately.

    python scripts/apply_lexicon_expansion.py --kb data/processed/fungramkb.json \\
        --candidates docs/lexicon_candidates.tsv --out data/processed/fungramkb_lex.json \\
        --approved-json data/extension/lexicon_expansion.json
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
from pathlib import Path

POS = {"entity": "n", "event": "v", "quality": "adj"}
PROVENANCE = "lexicon-expansion-2026-10-07"


def read_table(path: str) -> list[dict]:
    """The candidate table as edited by hand: UTF-8 / UTF-8 with BOM / UTF-16 (Excel "Unicode text"),
    tab-, semicolon- or comma-separated."""
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    first = text.splitlines()[0]
    delim = max(("\t", ";", ","), key=first.count)
    rows = list(csv.DictReader(text.splitlines(), delimiter=delim))
    # tolerate renamed headers such as "approve" or "aprobar"
    for r in rows:
        for k in list(r):
            if k and k.strip().lower().startswith(("approve", "aprob")):
                r["approve (1/0)"] = r[k]
    return rows


def approved_rows(path: str, accept_suggested: bool = False) -> list[dict]:
    """Rows marked 1; with ``accept_suggested`` also the suggested rows left blank (an explicit expert choice:
    reject a suggested row by marking it 0)."""
    rows = []
    for r in read_table(path):
        mark = (r.get("approve (1/0)") or "").strip()
        if mark == "1" or (accept_suggested and not mark and (r.get("suggested") or "").strip() == "1"):
            rows.append(r)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", default="data/processed/fungramkb.json")
    ap.add_argument("--candidates", default="docs/lexicon_candidates.tsv")
    ap.add_argument("--out", default="data/processed/fungramkb_lex.json")
    ap.add_argument("--approved-json", default="data/extension/lexicon_expansion.json")
    ap.add_argument("--accept-suggested", action="store_true",
                    help="also approve the suggested rows left blank (mark 0 to reject a suggested row)")
    a = ap.parse_args(argv)

    kb = json.loads(Path(a.kb).read_text(encoding="utf-8"))
    existing = {(lu["lang"], lu["lemma"].lower(), lu["concept"]) for lu in kb["lexicon"]}
    added = []
    for r in approved_rows(a.candidates, a.accept_suggested):
        key = (r["lang"], r["candidate"].lower(), r["concept"])
        if key in existing or r["concept"] not in {c["id"] for c in kb["concepts"]}:
            continue
        existing.add(key)
        added.append({"lemma": r["candidate"], "lang": r["lang"], "pos": POS[r["type"]], "concept": r["concept"],
                      "provenance": PROVENANCE, "source": f"wordnet:{r['wordnet_sense']}"})
    kb["lexicon"] = kb["lexicon"] + added
    kb["version"] = f"{kb.get('version', 'unknown')}+lex{len(added)}"
    Path(a.out).write_text(json.dumps(kb, ensure_ascii=False, indent=1), encoding="utf-8")
    marks = [(r.get("approve (1/0)") or "").strip() for r in read_table(a.candidates)]
    if not any(marks) and not a.accept_suggested:
        print("No row of the 'approve (1/0)' column is filled in: nothing to add. Mark rows with 1/0, or use "
              "--accept-suggested to approve the suggested rows that are not marked 0.")
    Path(a.approved_json).parent.mkdir(parents=True, exist_ok=True)
    if added or any(marks):
        Path(a.approved_json).write_text(json.dumps(added, ensure_ascii=False, indent=1), encoding="utf-8")
    by = collections.Counter((u["lang"], u["pos"]) for u in added)
    print(f"{len(added)} lexical units added -> {a.out} ({dict(by)})")


if __name__ == "__main__":
    main()
