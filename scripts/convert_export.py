"""P01 — convert the native FunGramKB TSV export (data/raw/*.tsv) into the canonical JSON.

Input files (tab-separated, double-quoted multi-line fields, Latin-1):
  concept.tsv     domain, concept id, thematic frame, meaning postulate, gloss (en), metaconcept, top type
  hypernym.tsv    child, parent (single inheritance in this export)
  word.tsv        lemma, sense, language (ENG/SPA/ITA), concept, pos
  cognicon.tsv    script id (@...), predications, temporal relations (eN -> eM [Before|During|Equals...]), domain, ?, description
  globalcrimeterm_concepts.tsv   English term -> concept (extra lexicon)
  thematic_schemata.tsv          metaconcept -> default thematic frame
Output: data/processed/fungramkb.json  (+ docs/kb_report.md via `fgkb check-kb`)

Known issue in the export: Spanish/Italian accented characters were lost ('?cido' = 'ácido').
Lemmas containing '?' are kept but flagged (`lemma_corrupt`) and excluded from linking.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from repair_lemmas import repair

csv.field_size_limit(10**8)
# Spanish names of the exported Cognicon scripts (the export only carries English ids)
SCRIPT_NAMES_ES = {
    "@COOKING_OREGANO_LEMON_CHICKEN_00": "cocinar pollo al limón con orégano", "@DRIVING_A_CAR_00": "conducir un coche",
    "@EATING_AT_RESTAURANTS_00": "comer en un restaurante", "@GOING_TO_THE_CINEMA_00": "ir al cine",
    "@GOING_TO_THE_DISCO_00": "ir a la discoteca", "@PAY_CARD_00": "pagar con tarjeta", "@PAY_CASH_00": "pagar en efectivo",
    "@READING_00": "leer", "@TAKING_A_TAXI_00": "coger un taxi", "@WATCHING_TELEVISION_00": "ver la televisión",
}
# lexical units of the export that are wrong (reported to the FunGramKB team): excluded from linking/NLG
KNOWN_LEXICON_ERRORS = {("weapon", "es", "+WEAPON_00")}  # English lemma filed as Spanish
LANG = {"ENG": "en", "SPA": "es", "ITA": "it"}
TOP = {"#ENTITY": "entity", "#EVENT": "event", "#QUALITY": "quality"}


def read(path: Path) -> list[list[str]]:
    with open(path, newline="", encoding="latin-1") as fh:
        return [r for r in csv.reader(fh, delimiter="\t") if r and any(x.strip() for x in r)]


def norm_corel(text: str) -> str:
    """One-line COREL: collapse whitespace/newlines, normalise spacing around ':' and roles."""
    t = re.sub(r"\s+", " ", text or "").strip()
    t = re.sub(r"\(\s*(e\d+)\s*:", r"(\1:", t)
    t = re.sub(r"\)\s+([A-Z][a-z]+)\b", r")\1", t)  # ') Agent' -> ')Agent'
    return t


def frame_from(concept_id: str, raw: str) -> str | None:
    raw = norm_corel(raw)
    if not raw:
        return None
    raw = raw.replace("[", "(").replace("]", ")")  # optional participants -> plain
    counter = iter(range(1, 50))
    raw = re.sub(r"\(x\)", lambda m: f"(x{next(counter)})", raw)  # schema frames use bare (x)
    return f"(e1: {concept_id} {raw})"


def convert(raw_dir: Path, out: Path, extensions: list[str] = ()) -> dict:
    concepts = read(raw_dir / "concept.tsv")
    hyp = read(raw_dir / "hypernym.tsv")[1:]
    parents: dict[str, list[str]] = defaultdict(list)
    for child, parent in hyp:
        parents[child.strip()].append(parent.strip())

    def top_of(cid: str, seen=None) -> str | None:
        seen = seen or set()
        if cid in TOP:
            return TOP[cid]
        for p in parents.get(cid, []):
            if p not in seen:
                t = top_of(p, seen | {cid})
                if t:
                    return t
        return None

    out_concepts = {}
    for row in concepts:
        row = (row + [""] * 7)[:7]
        dom, cid, frame, mp, gloss, meta, top = (x.strip() for x in row)
        stype = TOP.get(top) or top_of(cid) or "entity"
        primitive = mp.strip().lower() == "sp"  # semantic primitive: no postulate
        if primitive:
            mp = ""
        out_concepts[cid] = {
            "id": cid, "parents": parents.get(cid, [meta] if meta else []),
            "semantic_type": stype,
            "meaning_postulate": norm_corel(mp) or None,
            "thematic_frame": frame_from(cid, frame) if stype == "event" else None,
            "glosses": {"en": re.sub(r"\s+", " ", gloss)} if gloss else {},
            "provenance": "fungramkb-export", "domain": dom,
            **({"semantic_primitive": True} if primitive else {}),
        }
    # metaconcepts and any hypernym node not defined in concept.tsv
    for node in set(parents) | {p for ps in parents.values() for p in ps}:
        if node not in out_concepts and node.startswith("#"):
            out_concepts[node] = {"id": node, "parents": parents.get(node, []),
                                  "semantic_type": top_of(node) or "entity", "meaning_postulate": None,
                                  "thematic_frame": None, "glosses": {}, "provenance": "fungramkb-export"}
    # default frames for events without one, from the metaconcept's thematic schema
    schemata = {r[0].strip(): r[1].strip() for r in read(raw_dir / "thematic_schemata.tsv") if len(r) > 1}
    for c in out_concepts.values():
        if c["semantic_type"] == "event" and not c["thematic_frame"] and not c["id"].startswith("#"):
            anc = c["parents"][:]
            while anc:
                a = anc.pop(0)
                if a in schemata:
                    c["thematic_frame"] = frame_from(c["id"], schemata[a])
                    c["frame_source"] = f"schema:{a}"
                    break
                anc += parents.get(a, [])

    lexicon, seen = [], set()
    for row in read(raw_dir / "word.tsv"):
        if len(row) < 5:
            continue
        lemma, _sense, lang, cid, pos = (x.strip() for x in row[:5])
        key = (lemma.lower(), LANG.get(lang, lang.lower()), cid)
        if key in seen:
            continue
        seen.add(key)
        extra = {"lemma_corrupt": True, "export_error": "wrong language"} if key in KNOWN_LEXICON_ERRORS else {}
        if "?" in lemma:
            fixed = repair(lemma, key[1])
            extra = {"lemma_repaired_from": lemma} if fixed else {"lemma_corrupt": True}
            lemma = fixed or lemma
        lexicon.append({"lemma": lemma, "lang": key[1], "pos": {"a": "adj"}.get(pos, pos), "concept": cid, **extra})
    # globalcrimeterm_concepts.tsv holds Porter stems ("amphetamin") and ids absent from concept.tsv:
    # it is not used as lexicon (kept in data/raw for reference).
    for row in []:
        if len(row) >= 2:
            key = (row[0].strip().lower(), "en", row[1].strip())
            if key not in seen and row[1].strip():
                seen.add(key)
                lexicon.append({"lemma": row[0].strip(), "lang": "en", "pos": "n", "concept": row[1].strip()})

    scripts = []
    for row in read(raw_dir / "cognicon.tsv"):
        row = (row + [""] * 6)[:6]
        sid, body, rels, dom, _, desc = row
        preds = re.findall(r"[+*]\s*\(\s*\(?\s*e\d+:.*?(?=\r?\n\s*[+*]\s*\(|\Z)", body.strip(), flags=re.DOTALL)
        preds = [norm_corel(p) for p in preds]
        evars = [re.search(r"\(\s*\(?\s*(e\d+)\s*:", p).group(1) for p in preds]
        relations = [(a, b, r.strip()) for a, b, r in re.findall(r"(e\d+)\s*->\s*(e\d+)\s*\[([^\]]*)\]", rels)]
        # order: topological sort over Before edges, ties by evar number
        order = {e: i for i, e in enumerate(evars)}
        succ = defaultdict(set)
        indeg = {e: 0 for e in evars}
        for a, b, r in relations:
            if a in indeg and b in indeg and "Before" in r and b not in succ[a]:
                succ[a].add(b)
                indeg[b] += 1
        ready = sorted([e for e, d in indeg.items() if d == 0], key=lambda e: int(e[1:]))
        topo = []
        while ready:
            e = ready.pop(0)
            topo.append(e)
            for b in sorted(succ[e], key=lambda e: int(e[1:])):
                indeg[b] -= 1
                if indeg[b] == 0:
                    ready.append(b)
            ready.sort(key=lambda e: int(e[1:]))
        topo += [e for e in evars if e not in topo]
        steps = []
        for rank, e in enumerate(topo, 1):
            p = preds[order[e]]
            ev = re.search(r"e\d+\s*:\s*(?:[a-z]+\s+)*([+$#][A-Z0-9_]+)", p)
            steps.append({"order": rank, "predication": p, "event": ev.group(1) if ev else None,
                          "evar": e, "label": {}})
        names = {"en": sid.strip().lstrip("@").rsplit("_", 1)[0].replace("_", " ").lower()}
        if sid.strip() in SCRIPT_NAMES_ES:
            names["es"] = SCRIPT_NAMES_ES[sid.strip()]
        scripts.append({"id": sid.strip(), "name": names,
                        "participants": [], "steps": steps, "preconditions": [],
                        "relations": [list(r) for r in relations], "description": re.sub(r"\s+", " ", desc)})

    # authored extension (never overrides an exported concept)
    n_ext = 0
    for ext_path in extensions:
        payload = json.loads(Path(ext_path).read_text(encoding="utf-8"))
        ext_concepts = payload["concepts"] if isinstance(payload, dict) else payload
        for cid, lems in (payload.get("lemmas", {}) if isinstance(payload, dict) else {}).items():
            for lang, lem in lems.items():
                if (lem.lower(), lang, cid) not in seen:
                    seen.add((lem.lower(), lang, cid))
                    lexicon.append({"lemma": lem, "lang": lang, "pos": "", "concept": cid, "provenance": "authored-lemma"})
        for e in ext_concepts:
            if e["id"] in out_concepts:
                continue
            lemmas = e.pop("lemmas", {})
            out_concepts[e["id"]] = e
            n_ext += 1
            for lang, lem in lemmas.items():
                if lem and (lem.lower(), lang, e["id"]) not in seen:
                    seen.add((lem.lower(), lang, e["id"]))
                    lexicon.append({"lemma": lem, "lang": lang, "pos": {"entity": "n", "event": "v", "quality": "adj"}[e["semantic_type"]],
                                    "concept": e["id"], "provenance": e.get("provenance", "authored")})
    for c in out_concepts.values():  # default frames for authored events too
        if c["semantic_type"] == "event" and not c.get("thematic_frame") and not c["id"].startswith("#"):
            for a in c["parents"]:
                if a in schemata:
                    c["thematic_frame"] = frame_from(c["id"], schemata[a])
                    c["frame_source"] = f"schema:{a}"

    data = {"version": "fgkb-export-tsv" + ("+ext" if n_ext else ""), "concepts": list(out_concepts.values()), "lexicon": lexicon,
            "scripts": scripts, "instances": []}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--out", default="data/processed/fungramkb.json")
    ap.add_argument("--extension", action="append", default=[], help="authored concept JSON to merge")
    a = ap.parse_args()
    d = convert(Path(a.raw), Path(a.out), a.extension)
    print(f"{len(d['concepts'])} concepts, {len(d['lexicon'])} lexical units, {len(d['scripts'])} scripts -> {a.out}")
