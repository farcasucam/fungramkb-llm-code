# CLAUDE.md — fgkb-llm

Research code for paper 1 of the FunGramKB × LLM project: does FunGramKB deep semantics
(meaning postulates in COREL, thematic frames, Cognicon) improve **deep reasoning** in open
LLMs, and is the gain reasoning rather than recall? Target: ACM TIST special issue on
Knowledge-Informed LLMs, submission **15 Jan 2027**.

Master plan (Spanish, source of truth for research decisions):
"FunGramKB LLM – Guion del proyecto (v3)" in the project Google Drive folder.
If code and plan disagree, ask the user before changing either.

## Working with the user

- The user (Paco, FunGramKB author) writes in Spanish: **reply in Spanish**.
- Code, comments, docstrings, commit messages and docs inside the repo: **British English**
  (formalise, behaviour, modelling). The paper is written in LaTeX on Overleaf, also en-GB.
- Ask before changing research design: hypotheses, conditions, metrics, splits, gold definition.

## Commands

```bash
uv venv && uv pip install -e ".[dev,analysis]"     # CPU dev setup (add ",llm,controls" on the GPU box)
python tests/fixtures/make_toy_kb.py               # (re)build the toy KB fixture
pytest -q                                          # must stay green (45+ tests)
ruff check src tests
# real data (FunGramKB TSV export in data/raw, git-ignored)
python scripts/convert_export.py --extension data/extension/core_extension.json \
    --extension data/extension/lexicon_stubs.json --out data/processed/fungramkb.json
fgkb bench --kb data/processed/fungramkb.json --out data/processed/fgkb_reason.jsonl --deep
python scripts/validate_offline.py --bench data/processed/fgkb_reason.jsonl --kb data/processed/fungramkb.json \
    --out results/validation.json --report docs/validation_report.md
python scripts/kb_report.py --kb data/processed/fungramkb.json --bench data/processed/fgkb_reason.jsonl \
    --out docs/kb_report.md --nlg-sample docs/nlg_audit_sample.tsv
fgkb run --config configs/dryrun_real.yaml       # mock, deep contrast subset
scripts/run_pilot.sh                             # GPU only: go/no-go pilot + preregistered analysis
fgkb check-kb --kb tests/fixtures/toy_kb.json
fgkb bench    --kb tests/fixtures/toy_kb.json --out results/toy_bench.jsonl
fgkb run      --config configs/dryrun.yaml         # mock backend, end to end, no GPU
fgkb report   results/dryrun.jsonl --paper results/paper_dry
```

## Layout (src/fgkb_llm)

| Module | Role |
|---|---|
| `kb/` | KB data model + canonical JSON loader (`docs/DATA_FORMAT.md`) |
| `corel/` | Lark grammar of meaning postulates, AST, fact extraction, verbalisation (EN/ES), GBNF |
| `reasoner/asp.py` | clingo reasoner: strict/defeasible inheritance, exceptions, conflicts, traces = **gold source** |
| `graph/`, `retrieval/`, `controls/` | contexts for G1/G2/G4, R1/R2, G3 (WordNet), G4 (corrupted KB) |
| `conditions/prompts.py` | prompt builder for B0…F2, token budget, ablation switches (`ABLATIONS`) |
| `pipeline/neurosymbolic.py` | N1/N2: text → constrained COREL query → ASP → answer |
| `bench/` | FGKB-Reason generator, concept splits, balancing, item schema |
| `llm/backends.py` | mock / OpenAI-compatible (vLLM serve) / vLLM offline / transformers |
| `finetune/` | SFT data from seen concepts; LoRA/QLoRA training (GPU) |
| `eval/`, `analysis/` | answer parsing, metrics, bootstrap, McNemar, Holm, kappa; LaTeX tables into `paper/` |
| `runner.py`, `cli.py` | experiment matrix (resumable JSONL) and `fgkb` CLI |

## Invariants — do not break

- **The gold comes from the reasoner, never from an LLM.** No LLM-as-judge in primary metrics.
- All knowledge conditions get the **same token budget**; only the fact block differs between conditions.
- G4 (corrupted KB) keeps the taxonomy identical (`Reasoner(..., mp_isa=False)`).
- The concept linker is shared by all conditions.
- `test_unseen` concepts must never appear in LoRA training data.
- EN/ES twins share `pair_id`; balancing must keep twins together.
- The toy KB (`tests/fixtures`) is illustrative: **never report results on it**, never change its semantics
  (BIRD/OSTRICH follow Table 3-6 of the thesis).
- `tests/test_pipeline.py::test_oracle_accuracy` (> 97 %) guards the N1/N2 logic; keep it passing.
- **Primary analysis set = deep contrast subset** (`bench/contrast.py`): labels balanced per queried
  property, so question-only classifiers stay at or below the majority baseline (V4). Re-run
  `scripts/validate_offline.py` after any change to generators or NLG; V1 and V2 must stay at 100 %.
- Patched deep items: contexts come from `ContextBuilder.for_item` (the item's own KB); G4 never
  applies patch edits of existing concepts (it would leak the true postulate).
- NLG must return None rather than produce a garbled or mixed-language sentence.
- Keep public interfaces used by `runner.py` stable; add tests next to existing ones for every change.

## COREL notes (thesis, §3.1.7.2)

`+` strict / `*` defeasible predications; linked predications `*((e3: …) (e4: …))`; predication
operators (ing pro egr, rpast…rfut, cert prob pos obl adv perm, `n` polarity); quantifiers
(digits, m s p i); connectors & | ^; arguments `x`, satellites `f`; role written after `)`.
Unsupported yet: lambda connector, facts from linked/satellite predications (see P03).

## Roadmap (details and ready-to-use prompts in `docs/PROMPTS.md`)

Priority order:
1. DONE (Oct 2026): P01 converter (99.8 % postulates parse), P05 NLG, P13 proofs, P14/P15 deep suite,
   contrast subset, offline validation (`docs/validation_report.md`), pilot scripts.
2. NEXT: expert validation of authored concepts and of `docs/nlg_audit_sample.tsv` (Paco); GPU pilot
   (`scripts/run_pilot.sh`) before the go/no-go date.
3. P03 remaining COREL subset (lambda connector, facts from linked/satellite predications).
4. **P16** prompt families PR1–PR7 (numbered facts, JSON output, 3 wording variants, citation/step scoring).
5. **P17** mixed-effects analysis, power, hypothesis-only baselines, preregistration template.
6. P02–P12 as listed (NLG, paraphrasing, dense retrieval, external benchmarks, contamination, GPU infra, error analysis, Overleaf skeleton).

Key dates: preregistration 15 Nov 2026 · go/no-go 29 Nov 2026 (B1, G1–G4, N1 on 2 models, deep subset) · submission 15 Jan 2027.

## Paper (LaTeX)

The definitive paper sources live in `paper/` (its own git repository, remote
`https://github.com/farcasucam/fungramkb-llm-paper`). Edit the paper only there:
stage the current files from `paper/` first (the user may have edited them, e.g. via Overleaf or GitHub), edit, write them
back, and let the user commit and push (this environment cannot push to GitHub). `paper/` is ignored by this
repository's `.gitignore`. Pilot numbers are wrapped in `\pilot{}` and open items in `\todo{}` (`macros.tex`).
Result tables in `paper/tables/` are regenerated from `results/` with the analysis scripts.

## Data and secrets

`data/raw/` and `data/processed/*.json(l)` are git-ignored: never commit the FunGramKB export.
`results/` and `checkpoints/` are git-ignored too.
