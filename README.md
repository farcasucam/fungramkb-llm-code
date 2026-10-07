# fgkb-llm

Deep conceptual semantics from **FunGramKB** for open LLMs: a controlled comparison of
retrieval (RAG), GraphRAG, LoRA knowledge injection and a neuro-symbolic pipeline
(text → COREL → answer-set reasoning), evaluated on **FGKB-Reason**, a bilingual
(English/Spanish) benchmark of lexical-conceptual inference.

Code for paper 1 (target: ACM TIST, special issue on Knowledge-Informed LLMs).
Project script and design decisions: see the project Google Doc
*FunGramKB LLM – Guion del proyecto*.

## Layout

```
src/fgkb_llm/
  kb/          FunGramKB data model and canonical JSON loader
  corel/       COREL grammar (Lark), AST, fact extraction, verbalisation, GBNF for constrained decoding
  reasoner/    ASP (clingo) reasoner: strict/defeasible inheritance, traces, consistency checks
  graph/       postulates as predication nodes; budgeted linearisation for GraphRAG
  linking/     text -> concept linking with sense disambiguation
  retrieval/   RAG over verbalised postulates (TF-IDF default, dense optional)
  controls/    G3 generic KG (WordNet/ConceptNet), G4 corrupted KB
  bench/       FGKB-Reason generator, concept-level splits, balancing, JSONL schema
  conditions/  prompts for B0 B1 R1 R2 G1 G2 G3 G4 F1 F2 (+ ablation switches)
  pipeline/    N1 / N2 neuro-symbolic pipeline with verification loop
  llm/         backends: mock, OpenAI-compatible (vLLM server), vLLM offline, transformers
  finetune/    SFT data from seen concepts; LoRA/QLoRA training (TRL + PEFT)
  eval/        answer parsing, metrics, bootstrap, McNemar, Holm, inter-annotator kappa
  analysis/    LaTeX tables and figures into paper/ (synced with Overleaf)
configs/       experiment, LoRA, benchmark and dry-run YAML
docs/          CATALOGO_SCRIPTS.md (status of every script), PROMPTS.md (pending work), DATA_FORMAT.md
tests/         pytest suite on an illustrative toy KB (tests/fixtures)
```

## Quick start (no GPU)

```bash
uv venv && uv pip install -e ".[dev,analysis]"     # or: pip install -e ".[dev,analysis]"
python tests/fixtures/make_toy_kb.py
pytest -q
fgkb check-kb --kb tests/fixtures/toy_kb.json
fgkb bench    --kb tests/fixtures/toy_kb.json --out results/toy_bench.jsonl
fgkb run      --config configs/dryrun.yaml           # mock backend: numbers are meaningless
fgkb report   results/dryrun.jsonl --paper results/paper_dry
```

## Real experiment

```bash
python scripts/convert_export.py        # P01: native export -> data/processed/fungramkb.json
fgkb check-kb --kb data/processed/fungramkb.json
fgkb bench    --kb data/processed/fungramkb.json --out data/processed/fgkb_reason.jsonl --balance configs/bench.yaml
fgkb sft-data --kb data/processed/fungramkb.json --out data/processed/sft_train.jsonl
python -m fgkb_llm.finetune.train_lora --config configs/lora.yaml --seed 0   # x3 seeds
pip install -e ".[llm,controls]"
fgkb run      --config configs/experiment.yaml
fgkb report   results/main.jsonl --paper paper
```

The toy KB in `tests/fixtures` is illustrative (BIRD and OSTRICH follow Table 3-6 of
Arcas Túnez, 2008; everything else is a simplified stand-in). Never report results on it.

## Licence

Code: Apache-2.0. Benchmark data derived from FunGramKB: CC BY 4.0, with permission of the FunGramKB team.
