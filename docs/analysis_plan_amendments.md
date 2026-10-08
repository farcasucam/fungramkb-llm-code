# Amendments to the analysis plan (after tag `prereg-v1`)

`docs/analysis_plan.md` is frozen at tag `prereg-v1`. Changes made after the tag and before any main-study
response was generated are listed here, with the commit that introduced them. None changes data, conditions,
models, hypotheses, metrics or tests.

| Date | Commit / tag | Change | Why |
|---|---|---|---|
| 2026-10-08 | `main-run-v1` | `scripts/main_analysis.py` and `scripts/main_glmm.R`: implementation of sections 5, 7 and 8 | The plan fixed the tests; this is the code that runs them, written before any main-study data |
| 2026-10-08 | `main-run-v1` | `scripts/rerun_truncated.py` builds R1 contexts with the dense retriever of the config (`runner.make_encoder`) | Bug: regenerated R1 answers would otherwise have used TF-IDF contexts, unlike the rest of R1 |
| 2026-10-08 | `main-run-v1` | `scripts/spark_main_up.sh`, `scripts/run_main_windows.ps1`: one vLLM image for the three models, run order, server versions saved to `results/main_servers.json` | Section 3 (inference) |
| 2026-10-08 | (after the confirmatory run) | `scripts/rerun_truncated.py --out/--models/--conditions`: exploratory second regeneration at 2048 tokens of the Llama R1 rows still without answer, written to `results/main_rerun2048.jsonl`; `results/main.jsonl` (1024 tokens, confirmatory) unchanged | 60 Llama R1 answers enumerate every retrieved fact and hit the 1024-token limit |

## Exploratory condition N1P3 (after the confirmatory run, 8 Oct 2026)

Not part of the preregistered analysis; reported as exploratory.

- **Diagnosis.** On the W3 test results of N1P2, items answered correctly in W1 and wrongly in W3 (757 model-item
  pairs) were compared query by query: the event changed in 72 % (mostly an attribution paraphrased with a light
  verb, "involve violence", "have a small size"), the subject in 21 % (converse predication), the negation in 4 %;
  94 % of the wrong answers were "undetermined". This diagnosis used test data.
- **Method, fixed before applying it to test.** N1P3 = N1P2 (same parser, prompts and decoding) plus a deterministic
  re-reading of the queries the reasoner cannot decide (`pipeline/neurosymbolic.py::normalised`): light-verb or
  nominalised attribution as BE_01 with the quality; WordNet noun->quality and quality->quality equivalences
  (`scripts/build_equivalences.py`, 15 pairs, `docs/n1p3_equivalences.tsv`, pending expert review); the converse
  predication; event subsumption through the genus of the events' meaning postulates. Evaluated on the pilot dev
  split (W1/W2/W3) and frozen; then applied once to test.
- **Computation.** Because the parser is unchanged, N1P3 answers are obtained by re-deciding the queries N1P2
  generated (`scripts/n1p3_offline.py`), with no new LLM call; identical to running N1P3 live.
