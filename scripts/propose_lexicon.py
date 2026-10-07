"""Propose new lexical units (EN/ES) for FunGramKB concepts from WordNet / Open Multilingual Wordnet.

FunGramKB links several lexical units to one concept; the export has few per concept (155 events: 13 with
more than one English lemma), so the shared linker and N1P's event cue miss ordinary synonyms
("consume" for +INGEST_00, "imponer" for +PUT_00). Candidates come ONLY from WordNet, never from the
benchmark or its paraphrases, and are approved by a FunGramKB expert before use
(scripts/apply_lexicon_expansion.py).

For every concept with an English lemma: the first senses (--senses) of each English lemma with the
concept's part of speech give English synonyms (lemma names) and Spanish ones (OMW); Spanish lemmas of the
concept add their own senses. Qualities also take the lemmas of similar adjectives (WordNet satellites).
Candidates that are already lemmas of another concept are flagged (``conflict``), and very general verbs
(have, take, make, tener, tomar ...) are flagged as ``general``: both are left unapproved by default.

    python scripts/propose_lexicon.py --kb data/processed/fungramkb.json --bench data/processed/fgkb_reason_main.jsonl \\
        --out docs/lexicon_candidates.tsv
"""

from __future__ import annotations

import argparse
import collections
import csv

from fgkb_llm.bench.contrast import contrast_subset
from fgkb_llm.bench.schema import read_jsonl
from fgkb_llm.controls.generic_kg import _wordnet
from fgkb_llm.kb.loaders import load_json

POS = {"entity": "n", "event": "v", "quality": "a"}
# words of the question frames (W1/W2): as lemmas of an event they would cue it in every question
FRAME_WORDS = {"en": {"true", "correct", "answer", "say"}, "es": {"cierto", "correcto", "afirmar", "responder"}}
COPULAS = {"+BE_00", "+BE_01", "+BE_02"}  # their surface forms are handled by the verbaliser, not the lexicon
GENERAL = {"en": {"have", "take", "get", "make", "do", "be", "give", "go", "put", "set", "come", "keep", "hold",
                  "let", "run", "turn", "bring", "find", "see", "use", "work", "thing", "person", "one"},
           "es": {"tener", "tomar", "hacer", "dar", "ser", "estar", "poner", "ir", "llevar", "coger", "sacar",
                  "echar", "cosa", "persona", "uno", "haber", "quedar", "pasar"}}


def concept_frequency(bench_path: str) -> collections.Counter:
    """How often each concept is the focus, the event or the filler of a deep contrast item."""
    n = collections.Counter()
    for it in contrast_subset([i for i in read_jsonl(bench_path) if i.task == "deep"]):
        if it.lang != "en":
            continue
        n.update(it.focus_concepts[:1])
        prop = it.meta.get("prop") or []
        if prop:
            n[prop[0]] += 1
            if prop[3] and " " not in prop[3]:
                n[prop[3]] += 1
    return n


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", default="data/processed/fungramkb.json")
    ap.add_argument("--bench", default="data/processed/fgkb_reason_main.jsonl")
    ap.add_argument("--out", default="docs/lexicon_candidates.tsv")
    ap.add_argument("--senses", type=int, default=1, help="WordNet senses per lemma (most frequent first)")
    ap.add_argument("--max-per-concept", type=int, default=4)
    ap.add_argument("--min-items-entity", type=int, default=5,
                    help="entities are proposed only if they occur in at least this many contrast items")
    ap.add_argument("--all", action="store_true", help="also concepts that do not occur in the benchmark")
    a = ap.parse_args(argv)

    wn = _wordnet()
    kb = load_json(a.kb)
    freq = concept_frequency(a.bench)
    owner = collections.defaultdict(set)  # (lang, lemma) -> concepts
    for lu in kb.lexicon:
        owner[(lu.lang, lu.lemma.lower())].add(lu.concept)

    rows = []
    for cid, con in kb.concepts.items():
        if cid.startswith("#") or con.semantic_type not in POS or cid in COPULAS:
            continue
        if not a.all and (freq.get(cid, 0) == 0 or
                          (con.semantic_type == "entity" and freq.get(cid, 0) < a.min_items_entity)):
            continue
        pos = POS[con.semantic_type]
        current = {lang: [lem.lower() for lem in kb.lemmas(cid, lang)] for lang in ("en", "es")}
        if not current["en"]:
            continue
        cands = {"en": collections.OrderedDict(), "es": collections.OrderedDict()}

        def add(lang, lemma, syn, rank, current=current, cands=cands):
            lemma = lemma.replace("_", " ").lower()
            if lemma in current[lang] or len(lemma) < 3 or any(ch.isdigit() or ch == "-" for ch in lemma):
                return
            cands[lang].setdefault(lemma, (syn, rank))

        poses = ("a", "s") if pos == "a" else (pos,)
        for lemma in current["en"]:
            syns = [s for p in poses for s in wn.synsets(lemma.replace(" ", "_"), pos=p)][: a.senses]
            for rank, syn in enumerate(syns):
                for name in syn.lemma_names():
                    add("en", name, syn, rank)
                for name in syn.lemma_names("spa"):
                    add("es", name, syn, rank)
                if pos == "a":
                    for sim in syn.similar_tos()[:4]:
                        for name in sim.lemma_names():
                            add("en", name, sim, rank + 1)
                        for name in sim.lemma_names("spa"):
                            add("es", name, sim, rank + 1)
        for lemma in current["es"]:
            syns = [s for p in poses for s in wn.synsets(lemma.replace(" ", "_"), pos=p, lang="spa")][: a.senses]
            for rank, syn in enumerate(syns):
                for name in syn.lemma_names("spa"):
                    add("es", name, syn, rank)

        for lang in ("en", "es"):
            for lemma, (syn, rank) in list(cands[lang].items())[: a.max_per_concept]:
                others = sorted(owner.get((lang, lemma), set()) - {cid})
                flags = []
                if others:
                    flags.append("conflict:" + ",".join(others))
                if lemma in GENERAL[lang] or lemma.split()[0] in GENERAL[lang]:
                    flags.append("general")
                if lemma in FRAME_WORDS[lang]:
                    flags.append("question-frame word")
                rows.append({"concept": cid, "type": con.semantic_type, "lang": lang, "n_items": freq.get(cid, 0),
                             "current_lemmas": " | ".join(current[lang]), "candidate": lemma,
                             "wordnet_sense": syn.name(), "sense_rank": rank, "gloss": syn.definition(),
                             "flags": " ".join(flags),
                             "suggested": "" if flags or rank > 0 else "1", "approve (1/0)": ""})

    order = {"event": 0, "quality": 1, "entity": 2}
    rows.sort(key=lambda r: (order[r["type"]], -r["n_items"], r["concept"], r["lang"], r["sense_rank"]))
    with open(a.out, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    by_type = collections.Counter((r["type"], r["lang"]) for r in rows)
    print(f"{len(rows)} candidates for {len({r['concept'] for r in rows})} concepts -> {a.out}")
    print(dict(by_type))
    print("flagged:", sum(bool(r["flags"]) for r in rows))


if __name__ == "__main__":
    main()
