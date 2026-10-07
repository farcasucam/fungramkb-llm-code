# Analysis plan — main study (frozen before data collection)

**Status:** frozen with git tag `prereg-v1`. A copy (PDF or this file) may be deposited on Zenodo/OSF for a timestamp.
**Paper:** "Reasoning with Meaning Postulates: FunGramKB Deep Semantics for Knowledge-Informed Open Language Models"
(ACM TIST, special issue on Knowledge-Informed LLMs).
**Authors:** F. Arcas-Túnez (UCAM), C. Periñán-Pascual (UPV).

This plan fixes the data, conditions, models, metrics, hypotheses and tests of the confirmatory study **before** any
main-study response is generated. Everything that was decided after looking at data (the pilot and the dev runs) is
listed in §10 as a deviation from the pilot protocol. Analyses not listed in §5–§7 are exploratory and are reported as such.

## 1. Data

- **Knowledge base:** `data/processed/fungramkb.json`, i.e. the FunGramKB export plus the authored extension, with
  584 concepts. The SHA-256 of the file, of the benchmark, of the config and of the source code, plus the git tag, are recorded at run time in `results/main_manifest.jsonl` (`runner.write_manifest`).
  - The lexicon-expanded KB (`fungramkb_lex.json`) is **not** used in the confirmatory runs (see §8).
- **Benchmark:** `data/processed/fgkb_reason_main.jsonl`, built by `scripts/make_main_bench.py` with seed **2027**.
  - Gold labels come from the ASP reasoner (`reasoner/asp.py`), never from an LLM.
  - Items that repeat a pilot dev item were moved to `dev`.
- **Analysis set:** the deep contrast subset (`bench/contrast.py`, `contrast_over: [test_seen, test_unseen, dev]`),
  restricted to the splits `test_seen` and `test_unseen`.
  - Size: 1484 items (EN+ES); 776 of them are pilot-disjoint (`meta.pilot_overlap = none`).
  - Labels are balanced per queried property: yes / no / undetermined.
  - EN/ES twins share `pair_id`, which is the clustering unit of every test.
- **Dev:** the `dev` split is the only split used for tuning. No test item is inspected before the analysis.

## 2. Conditions

All conditions share the concept linker and a 1500-token context budget. Only the fact block differs between conditions.

| Code | Context / method |
|---|---|
| B1 | No knowledge (question only, same instructions and output format) |
| G1 | FunGramKB taxonomy only (IS-A facts, verbalised) |
| G2 | FunGramKB taxonomy + meaning postulates, verbalised (graph context of the linked concepts) |
| G3 | Generic lexical KG of the same size: WordNet / OMW hypernyms and glosses |
| G4 | Corrupted FunGramKB: same taxonomy, postulates shuffled across concepts (`mp_isa=False`) |
| R1 | Plain RAG over verbalised postulates, **dense retriever** `intfloat/multilingual-e5-base` (§10) |
| N1R | Neuro-symbolic: LLM → COREL query (role-tolerant decision) → ASP reasoner → answer |
| N1P2 | N1R with the subject pinned to the interrogative clause, a slot schema (negated/subject/event/object), event cues from NLG morphology and light verbs, relational events and all qualities |

Decoding is constrained by a JSON schema (equivalent to the GBNF grammar). The answer labels are
yes / no / undetermined.

## 3. Models and inference

- Qwen2.5-7B-Instruct, Llama-3.1-8B-Instruct and OLMo-3-7B-Instruct, all in bf16.
- All three are served by vLLM with **the same NGC image** `nvcr.io/nvidia/vllm:26.09-py3` on the DGX Spark.
- Decoding: temperature 0, seed 0, `max_tokens` 1024.
- Responses cut at `max_tokens` are regenerated **once** with the same settings (`scripts/rerun_truncated.py`).
- Configs: `configs/main_qwen_llama.yaml`, `configs/main_olmo.yaml` and `configs/main_wordings_*.yaml`, as of tag `prereg-v1`.

## 4. Outcome measures

**Primary outcome:** accuracy (exact label match) per item. An unparsed or missing answer counts as incorrect.

**Secondary outcomes:**

- balanced accuracy (mean recall per gold label);
- macro-F1 over the three labels;
- % of «undetermined» predictions, compared with the gold share;
- for N1*, coverage (share of items where the parser produced an executable query) and accuracy on covered items.

## 5. Confirmatory hypotheses

Every test is run **per model**, with α = 0.05.

- **H1 (primary): FunGramKB deep semantics help.**
  - Hypothesis: accuracy(G2) > accuracy(B1).
  - Test: one-sided paired cluster t-test over `pair_id` clusters.
  - H1 is declared supported if it is significant in at least 2 of the 3 models. All three results are reported.
- **H1u: transfer to unseen concepts.** The same contrast on `test_unseen` only.
- **H2: it is the right knowledge, and its structure matters.** This family is Holm-corrected within each model:
  - (a) G2 > G1 (postulates add over taxonomy);
  - (b) G2 > G3 (FunGramKB over a generic lexical KG of equal size);
  - (c) G2 > G4 (correct over corrupted postulates);
  - (d) G2 > R1 (structured graph context over dense text RAG).
- **H2-null: corrupted postulates do not beat the taxonomy.**
  - Hypothesis: G4 does not exceed G1.
  - Test: two one-sided tests (TOST) with equivalence margin ±3 points.
  - Reported with its 90 % CI.
- **H3: an external reasoner helps a model that follows context poorly.**
  - Hypothesis: N1P2 vs G2, two-sided, outside the Holm family.
  - Direction is not predicted; the pilot showed opposite signs for Qwen and Llama. The result is reported as confirmatory evidence for or against a model-dependent effect.

**Statistics for every contrast:**

- difference in accuracy, with a 95 % cluster-bootstrap CI (2000 resamples over `pair_id`);
- p-value of the paired cluster t-test;
- exact McNemar test on EN items, as a check.

**Pooled model.** A logistic mixed model provides the pooled estimate:

`correct ~ condition * model + (1 | pair_id) + (1 | focus_concept)`

- G2 is the reference level.
- Fitted with `lme4::glmer`; if it does not converge, `statsmodels` `BinomialBayesMixedGLM` is used instead.
- Conclusions must agree in sign with the per-model tests; disagreements are reported.

## 6. Robustness to wording (secondary, confirmatory in sign only)

- **Benchmark:** `data/processed/fgkb_reason_main_wordings.jsonl` (`scripts/make_wordings.py`).
  - W2: rule-based inversion plus approved synonyms.
  - W3: Mistral-Small-3.2-24B paraphrases that pass the automatic filters. The human audit gave 88 % precision after filtering.
- **Conditions:** B1, G2, G3 and N1P2, with the same three models.
- **Claim:** G2 − B1 > 0 holds in W2 and in W3, i.e. the bootstrap CI excludes 0 in at least 2 of the 3 models.
- **Also reported:**
  - accuracy per wording;
  - maximum drop from W1;
  - answer consistency across wordings;
  - W3 split by `subject_changed`.
- Analysis script: `scripts/wording_analysis.py`.

## 7. Diagnostics: reasoning, not recall (descriptive, 95 % bootstrap CIs)

- **Evidence sensitivity on ablation pairs:** the share of pairs where the model answers the intact item correctly *and* switches to «undetermined» when the required fact is removed.
- **Counterfactual compliance:** accuracy on affected items compared with their controls.
- **Exceptions:** accuracy on exception and exception-of-exception items.
- **Novel concepts:** accuracy on pseudoword concepts.
- **Depth:** accuracy by inference depth for each condition. The slope of the G2 − B1 difference across depth comes from the mixed model with a `condition × depth` term.

## 8. Sensitivity and ablation analyses (pre-specified, not confirmatory)

- **S1 (pilot-disjoint items):** all of §5 repeated on the 776 pilot-disjoint items.
- **S2 (EN only and ES only):** language-specific results.
- **S3 (lexicon expansion):** N1P2 and G2 with `fungramkb_lex.json`.
  - Reported as an ablation. On dev it had no effect (±3 points).
- **S4 (G2 ablations):** `conditions/prompts.py::ABLATIONS`, i.e. no thematic frames, no defeasible marks and no proofs, on Qwen.
- **S5 (balanced accuracy and macro-F1):** H1 and H2 recomputed with these measures.

## 9. Exclusions and missing data

- Items are never excluded after generation.
- If the reasoner or the NLG fails while a benchmark item is being built, the item is not generated. This is fixed by the benchmark file.
- If a response is still empty after one regeneration, it counts as incorrect. Its count is reported per model and condition.
- If a server crash makes a model × condition cell incomplete, the cell is resumed (`fgkb run` is resumable) with the same image and settings.
- If a model cannot be served with the frozen image, it is replaced by its predecessor in the same family, and this is reported as a deviation.

## 10. Changes with respect to the pilot (declared)

- `max_tokens` 384 → 1024.
- JSON-schema constrained decoding in every condition.
- N1 without `+BE_00` in the deep task.
- Balanced accuracy and macro-F1 added as secondary outcomes.
- New conditions:
  - G3 (WordNet control);
  - N1R (role-tolerant N1);
  - N1P2 (pinned slots, relational events, all qualities). N1P2 was developed on `dev` only (104 items) and replaces N1 as the main neuro-symbolic condition.
- R1 retriever: TF-IDF over character n-grams (pilot) → dense multilingual-e5-base (main), so that G2 > R1 is not won against a weak baseline. The TF-IDF R1 may be reported as exploratory.
- Third model family: OLMo-3-7B-Instruct, with open training data.
- One vLLM image (26.09) for all models. The pilot used 25.09 for Qwen and Llama.
- New benchmark sample (seed 2027), with pilot-dev overlaps moved to dev.

## 11. Exploratory (outside this plan)

- LoRA conditions F1/F2 (fine-tuning on `test_seen`-free data);
- a ~70B model;
- contamination check (OLMo data);
- error analysis of N1P2 parses.

These analyses are reported as exploratory.
