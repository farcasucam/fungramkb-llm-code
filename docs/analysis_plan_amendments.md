# Amendments to the analysis plan (after tag `prereg-v1`)

`docs/analysis_plan.md` is frozen at tag `prereg-v1`. Changes made after the tag and before any main-study
response was generated are listed here, with the commit that introduced them. None changes data, conditions,
models, hypotheses, metrics or tests.

| Date | Commit / tag | Change | Why |
|---|---|---|---|
| 2026-10-08 | `main-run-v1` | `scripts/main_analysis.py` and `scripts/main_glmm.R`: implementation of sections 5, 7 and 8 | The plan fixed the tests; this is the code that runs them, written before any main-study data |
| 2026-10-08 | `main-run-v1` | `scripts/rerun_truncated.py` builds R1 contexts with the dense retriever of the config (`runner.make_encoder`) | Bug: regenerated R1 answers would otherwise have used TF-IDF contexts, unlike the rest of R1 |
| 2026-10-08 | `main-run-v1` | `scripts/spark_main_up.sh`, `scripts/run_main_windows.ps1`: one vLLM image for the three models, run order, server versions saved to `results/main_servers.json` | Section 3 (inference) |
