# KB audit report

KB version: `fgkb-export-tsv+ext`

## Concepts

| Provenance | concepts | with meaning postulate | facts extracted |
|---|---|---|---|
| fungramkb-export | 419 | 360 | 223 |
| authored-2026-10-05 | 134 | 72 | 79 |
| stub-lemma-only-2026-10-05 | 31 | 0 | 0 |

Semantic types (non-meta): entity 378, event 136, quality 28

Taxonomic depth below the metaconcept layer: 0: 223, 1: 86, 2: 65, 3: 106, 4: 55, 5: 7

## Meaning postulates

432 postulates; 431 parse (99.8 %); 302 property facts, 334 IS-A links read from BE_00 classifications.

Parse errors (to be fixed in the KB, reported to the FunGramKB team):

- `+CONTRACT_KILLER_00`: No terminal matches ')' in the current parser context, at line 1 col 208

## Lexicon

Lexical units by language: es 783, en 742, it 360; Spanish lemmas with accents restored from the Latin-1 export: 168; unrecoverable (excluded): 3.

## Cognicon

10 scripts, 136 steps.

## Benchmark (EN; ES twins identical in number)

| Task | block | items |
|---|---|---|
| consistency |  | 3252 |
| deep | ablation | 221 |
| deep | counterfactual | 193 |
| deep | deep_real | 559 |
| deep | exceptions | 126 |
| deep | novel | 503 |
| deep | undet_control | 119 |
| deep | undetermined | 276 |
| entailment |  | 3592 |
| grounding |  | 13 |
| multihop |  | 2186 |
| procedural |  | 365 |

An expert-rating sample of 120 items (stratified by block) is in `docs/nlg_audit_sample_main.tsv`.
