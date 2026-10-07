# Canonical KB format (`data/processed/fungramkb.json`)

One JSON object, UTF-8. Produced from the native export by `scripts/convert_export.py` (P01).

## Native export (`data/raw/*.tsv`, tab-separated, Latin-1, no header unless stated)

| File | Columns |
|---|---|
| `concept.tsv` | domain, concept id, thematic frame, meaning postulate (`sp` = semantic primitive), English gloss, metaconcept, top type |
| `hypernym.tsv` | header `concept1 concept2`; child, parent |
| `word.tsv` | lemma, sense number, language (ENG/SPA/ITA), concept, part of speech |
| `cognicon.tsv` | script id (`@...`), predications (one per line, quoted), temporal relations (`eN -> eM [Before|During|Equals]`), domain, flag, description |
| `thematic_schemata.tsv` | metaconcept, default thematic frame with bare `(x)` slots |
| `selectionpref.tsv`, `arguments.tsv`, `construct.tsv`, `descript*.tsv`, `stoplist.tsv`, `globalcrimeterm_concepts.tsv` | kept for reference; not used (the last one holds Porter stems) |

Known export issues (reported in `docs/kb_report.md`): lost Spanish accents (`?`, repaired from
word frequencies, 2 unrecoverable lemmas excluded), one unbalanced postulate
(`+CONTRACT_KILLER_00`), one English lemma filed as Spanish (`weapon`).

## Provenance

Every concept carries `provenance`: `fungramkb-export`, `authored-2026-10-05` (written for this
project from the thesis conventions; pending expert validation) or `stub-lemma-only-2026-10-05`
(lemmas and parent only, no postulate). Lexical units may carry `lemma_repaired_from`,
`lemma_corrupt` or `provenance: authored-lemma`. Results are reported separately for items whose
proof uses only exported knowledge.

```json
{
  "version": "fgkb-20261020-ab12cd34",
  "concepts": [
    {
      "id": "+BIRD_00",                       // prefix: # metaconcept, + basic, $ terminal
      "parents": ["+VERTEBRATE_00"],          // one or more (multiple inheritance)
      "semantic_type": "entity",              // entity | event | quality
      "meaning_postulate": "+(e1: +BE_00 (x1: +BIRD_00)Theme (x2: +VERTEBRATE_00)Referent) *(e3: +FLY_00 (x1)Agent (x1)Theme)",
      "thematic_frame": null,                 // events: "(e1: +EAT_00 (x1: +ANIMAL_00)Agent (x2: +FOOD_00)Theme)"
      "glosses": {"en": "...", "es": "..."}
    }
  ],
  "lexicon": [
    {"lemma": "bird", "lang": "en", "pos": "n", "concept": "+BIRD_00"},
    {"lemma": "pájaro", "lang": "es", "pos": "n", "concept": "+BIRD_00"}
  ],
  "scripts": [
    {
      "id": "EAT_IN_RESTAURANT",
      "name": {"en": "eating in a restaurant", "es": "comer en un restaurante"},
      "participants": ["+HUMAN_00", "+RESTAURANT_00"],
      "steps": [{"order": 1, "predication": "(e1: +ENTER_00 (x1: +HUMAN_00)Agent)",
                 "label": {"en": "enter the restaurant", "es": "entrar en el restaurante"}}],
      "preconditions": ["+MONEY_00"]
    }
  ],
  "instances": [
    {"id": "MADRID_00", "concept": "+CITY_00", "names": {"en": "Madrid", "es": "Madrid"}}   // keep the id exactly as in the export
  ]
}
```

COREL is stored as plain text on one line: subscripts flattened (`x1`, `e2`, `f1`), the
role written right after the closing parenthesis (`(x1)Theme`), `+` strict and `*`
defeasible reasoning operators, and `n` for polarity.

# Benchmark item (`fgkb_reason.jsonl`)

See `src/fgkb_llm/bench/schema.py`. Key fields: `task`, `lang`, `question`, `options`,
`gold`, `depth`, `trace` (reasoner support), `distractor`, `pair_id` (EN/ES twins),
`split` (`dev`, `test_seen`, `test_unseen`).

Deep items (`task = "deep"`) add in `meta`: `block`, `prop` (queried property key),
`required_facts` (minimal proof), `reasoning_types`, `kb_patch` (novel / counterfactual /
ablation items: contexts and gold use exactly the patched KB), `cf_kind`, `contrast_of`.

# Result row (`results/*.jsonl`)

`item_id, task, lang, split, depth, distractor, pair_id, gold, pred, model, condition,
raw, config_hash` plus `ctx_tokens`, and for N1/N2 `trace`, `trace_ok`, `attempts`,
`kb_status`, `fallback`.
