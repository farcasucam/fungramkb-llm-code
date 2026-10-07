# Prompts de desarrollo para las piezas pendientes

Cada prompt está pensado para pegarlo en un asistente de código (Claude Code u otro) abierto **en la raíz de este repositorio**. Están en inglés porque el código y los comentarios del repositorio también lo están. Todos comparten las mismas reglas:

> Read `README.md`, `docs/DATA_FORMAT.md` and the module named below before writing code. Keep the public interfaces used by `runner.py` unchanged. Add pytest tests next to the existing ones; `python -m pytest -q` must stay green. British English in docstrings and comments. Do not change `tests/fixtures/toy_kb.json` semantics.

---

## P01 — Conversor de la exportación nativa de FunGramKB

```
Task: write scripts/convert_export.py that converts the native FunGramKB export in
data/raw/ into the canonical JSON described in docs/DATA_FORMAT.md, loadable by
fgkb_llm.kb.load_json.

Step 1 (inspection, report back before coding): list the files in data/raw/, their
format (XML / SQL dump / CSV / other) and print 3 sample records for: concepts
(with superordinates), meaning postulates, thematic frames, lexical units (EN and
ES), Cognicon scripts, Onomasticon instances. Identify how multiple inheritance,
semantic type (entity/event/quality) and concept level (#, +, $) are encoded.

Step 2: implement the mapping with streaming parsing (lxml.iterparse for XML,
sqlite3/csv for tabular dumps). Keep COREL text verbatim but normalise subscripts
(x<sub>1</sub> -> x1), role labels written as subscripts or suffixes
((x1)<sub>Theme</sub> -> (x1)Theme) and any Unicode lambda to the token LAMBDA.
Cognicon steps must become {order, predication, label:{en,es}}; if steps carry no
natural-language label, derive one from the event's first lexical unit.

Step 3: run `fgkb check-kb --kb data/processed/fungramkb.json` and write
docs/kb_report.md with counts per level and type, % of postulates that parse, the
20 most frequent parse errors with examples, and orphan concepts.

Acceptance: load_json succeeds; validate() returns no structural problems; >= 95 %
of postulates parse (otherwise list the failing constructions for P03).
```

## P02 — Versionado de la KB

```
Task: add scripts/freeze_kb.py that copies data/processed/fungramkb.json to
data/processed/fungramkb-<YYYYMMDD>-<sha8>.json, writes its SHA-256, counts and the
git commit into data/processed/KB_VERSION.json, and make runner.py record that
KB version id in every result row (field "kb_version"). Add a test.
```

## P03 — Cobertura completa de COREL

```
Task: extend src/fgkb_llm/corel/corel.lark, ast.py, parser.py and facts.py so that
>= 99 % of the meaning postulates in data/processed/fungramkb.json parse, using the
failing examples listed in docs/kb_report.md (P01). Known gaps:
(1) the lambda connector (empty conjunction) between predications, arguments or
satellites; (2) any quantifier or operator found in the export but not in
Tables 3-7/3-8 of the thesis (ask before inventing semantics); (3) facts.py only
uses the first predication of a linked group: add an option that also emits
facts about entities co-indexed through the link (e.g. OSTRICH has long legs:
Prop(+COMPRISE_00, Theme, Referent, +LEG_00) qualified by (+BE_01 Attribute +LONG_00))
as a nested Prop with a `qualifier` field, without changing Prop.key for existing facts;
(4) satellites whose filler is a predication (Reason, Condition, Purpose, Scene):
emit `ComplexFact` records kept for verbalisation, not used by the reasoner.
Add round-trip tests for every new construction and keep all existing tests green.
```

## P04 — Expansión MicroKnowing y razonamiento de cualidades

```
Task: implement in src/fgkb_llm/reasoner/microknowing.py the "meaning postulate
expansion" of the thesis (section 5.3.1): recursively replace a basic concept in a
predication by its own postulate until only semantic primitives (basic concepts
whose superordinate is a metaconcept, Concept.is_primitive) remain, with a depth
limit and cycle detection. Expose expand(concept, depth) -> list[Fact] and use it
in Reasoner when Reasoner(kb, expand_depth=k) is set. Then implement the cognitive
dimension of qualities (section 5.5): for gradable qualities (e.g. +HOT_00 vs +WARM_00)
read the "+(e2: BE (x2)Theme (x3: DIMENSION)Referent)" pattern and the m/s/p
quantifiers to order qualities on a scale, so that queries like "is X hotter than
warm?" can be answered. Tests on small hand-written KBs; the toy KB must still pass.
```

## P05 — Generación en lenguaje natural de calidad (ES/EN)

```
Task: improve src/fgkb_llm/corel/verbalize.py. Spanish needs gender and number
agreement (un/una, el/la, adjective agreement) using the lexicon's gender attribute
(add LexicalUnit.gender if the export provides it; otherwise a fallback heuristic
plus a small exceptions list), correct verb conjugation for irregular verbs and
reflexives, and natural prepositions per role. English needs correct articles,
plurals and irregular third-person forms. Keep `hedge=False` semantics. Add
golden-sentence tests for at least 40 facts (20 EN, 20 ES) from the real KB.
```

## P06 — Paráfrasis y revalidación de ítems

```
Task: write scripts/paraphrase_items.py. For every item in a benchmark JSONL,
ask a paraphrasing LLM (configurable; must be a different family from the evaluated
models) for 1 natural paraphrase of question/premise/hypothesis in the same language,
preserving meaning, negation and quantities. Then re-validate: run the item's
concepts through ConceptLinker and check that the linked focus concepts are the same
as before; for entailment/consistency items also run NeuroSymbolic with an oracle
query built from item.meta (see tests/test_pipeline.py) to confirm the gold label
is unchanged. Discard paraphrases that fail; keep the template version instead and
record "paraphrase_status" in item.meta. Output a new JSONL and a CSV of 50 random
pairs (template vs paraphrase) for a quick human check.
```

## P07 — Recuperación densa, embeddings y lematización

```
Task: (a) add an embedding backend for retrieval/rag.py using sentence-transformers
with a multilingual model (configurable; default a multilingual E5- or BGE-family
model), with on-disk caching of document embeddings keyed by KB version;
(b) add an embedding scorer for ConceptLinker.disambiguate comparing the sentence
with each sense's verbalised postulate; (c) add a spaCy lemmatiser adapter
(es_core_news_md, en_core_web_md) used when available. Expose all three through
the experiment YAML (retriever: tfidf|dense, linker_scorer: lesk|embedding,
lemmatiser: simple|spacy). Report linker accuracy on the grounding items as a test
utility (scripts/eval_linker.py).
```

## P08 — Benchmarks externos y ConceptNet

```
Task: write scripts/external_benchmarks.py that converts external datasets into
fgkb_llm.bench.schema.Item records (task="entailment" or "procedural"/"multihop" as
appropriate, split="external"):
- XNLI (es, en) test; lexical-inference subsets of SNLI/MNLI (pairs whose hypothesis
  differs from the premise by one content word, or an existing lexical NLI subset);
- COPA / XCOPA-style event-causality items, mapped to 2-option multiple choice;
Load via the `datasets` library. For each item compute FunGramKB coverage = share
of content lemmas linked by ConceptLinker; write coverage stats to
docs/external_coverage.md and keep a `covered` flag in meta. Also implement a
ConceptNet edge provider for controls/generic_kg.py (local CSV dump preferred over
the public API) with the same token budget logic.
```

## P09 — Sondeo de contaminación

```
Task: write scripts/contamination_probe.py. For 300 random meaning postulates,
prompt each evaluated model with the concept id and the first half of the COREL
string and measure exact and normalised-edit-distance completion of the second
half; also ask it to "write the FunGramKB meaning postulate of <concept>". Compare
against a baseline of shuffled concept ids. Output a table for the paper's
limitations section. Use the runner backends.
```

## P10 — Infraestructura GPU

```
Task: (a) scripts/serve_vllm.sh to start `vllm serve` for a model with
--enable-lora and the LoRA modules from configs; (b) Slurm templates in
scripts/slurm/ for train_lora (3 seeds as an array job) and for runner jobs per
model; (c) make llm/backends.py robust to vLLM API changes: detect whether
GuidedDecodingParams or the newer structured-outputs parameters are available and
use the right one; if neither is present, fall back to unconstrained decoding and
log a warning. Document GPU memory per model size in docs/compute.md.
```

## P11 — Análisis de errores

```
Task: write scripts/error_analysis.py that reads results JSONL and the benchmark
and produces, per model x condition, a categorised sample of errors: linking error
(focus concept not among linked seeds), COREL error (N1/N2 attempts with
validation errors, by error type), KB coverage gap (reasoner status unknown),
distractor failure (item.distractor and wrong), and reasoning error (rest). Output
docs/error_analysis.md with counts and 5 examples per category, plus the trace for
N1/N2 examples.
```

## P12 — Esqueleto del paper en Overleaf

```
Task: create paper/main.tex with \documentclass[acmsmall,screen,review]{acmart},
British English (babel british), sections as in section 19 of the project script,
\input{tables/main_results.tex}, \includegraphics{figures/depth_curve.pdf},
references.bib with the starting references from the project script, and a
macros.tex with consistent terms (\fgkb, \corel, meaning postulate, Cognicon,
Onomasticon). Keep it compiling with an empty results table.
```

---

# Prompts añadidos en la v2 del guion (gold standard y razonamiento profundo)

## P13 — Prueba mínima, hechos necesarios y profundidad

```
Task: extend src/fgkb_llm/reasoner/asp.py so every answer carries a *minimal proof*:
an ordered list of rule applications (isa-step, postulate-application, exception-block,
filler-chaining, frame-check, script-check) and the minimal set of KB facts it needs
(`required_facts`, ids of Fact/IsA records). Add filler chaining: if X has part P
(e.g. +COMPRISE_00 Referent +WING_00) and P's own postulate states Q, derive
"X has something that Q" with depth +1 (configurable max chain length).
Redefine depth = number of rule applications in the minimal proof (keep the old
IS-A-hop depth as `isa_depth`). Store proof, required_facts, reasoning_types and
3-valued label (true/false/undetermined) in bench.schema.Item (new optional fields,
backwards compatible). Tests: hand-built KBs with known proofs of length 1–4, an
exception-of-exception case, and a filler-chaining case on the toy KB
("does an ostrich have something with feathers?").
```

## P14 — Suite de razonamiento profundo

```
Task: add src/fgkb_llm/bench/deep_suite.py generating, with gold from the reasoner:
(a) novel concepts: pseudowords obeying EN/ES phonotactics (check they are not real
words in either lexicon or a word list), inserted as terminal concepts under a real
parent with 1–2 postulates; questions of depth 2–4 about them; definition sentence
stored in item.meta["definition"] so every condition can receive it;
(b) counterfactual KBs: copy of the KB with one postulate flipped or replaced
(KB variant id in item.meta), questions whose gold changes because of it;
(c) chained exceptions: default / exception / exception-of-exception at varying depth;
(d) undetermined items (open world). Balance by depth and label; EN/ES twins.
Tests verify the gold of each block with the reasoner on the toy KB.
```

## P15 — Ablación de evidencia y distractores

```
Task: add src/fgkb_llm/bench/evidence.py. For an item with required_facts (P13),
build three contexts with the same token budget: full; minus one required fact
(gold becomes "undetermined" unless another proof exists — recompute with the
reasoner); minus one irrelevant fact. Also a distractor variant adding plausible
but irrelevant facts from sibling concepts. Expose as conditions G2-full,
G2-minus-required, G2-minus-irrelevant, G2-distractor in conditions/prompts.py and
add the metric evidence_sensitivity = P(change | minus required) - P(change | minus
irrelevant) to eval/metrics.py. Tests on the toy KB.
```

## P16 — Familias de prompts PR1–PR7

```
Task: add src/fgkb_llm/conditions/deep_prompts.py implementing families PR1–PR7 of
the project script (section 15): numbered facts [F1]…, explicit "undetermined"
option, priority instruction ("if the facts contradict what you know, follow the
facts"), JSON output {"answer", "steps":[{"claim","facts"}], "confidence"} validated
with a JSON schema (and passed to vLLM as structured output when available),
3 wording variants per family, EN and ES. Add scoring in eval/: citation precision
and recall against required_facts, step accuracy against the gold proof, and ECE
from confidence. The fact block is the only thing that changes across conditions.
```

## P17 — Análisis estadístico y preregistro

```
Task: add src/fgkb_llm/analysis/mixed.py fitting the primary model
correct ~ condition * depth + lang + (1|concept) + (1|template) + (1|model)
(statsmodels BinomialBayesMixedGLM, or lme4 through rpy2 if available), reporting
odds ratios with 95% CI and the condition×depth interaction for G2 vs B1, G1, G3.
Add power.py (McNemar sample size, as in the project script), hypothesis-only and
question-only baselines (V4) and docs/preregistration.md with H1, H2, primary
metric, deep subset definition, models and exclusion rules, ready for OSF.
```
