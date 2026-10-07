#!/usr/bin/env bash
# Go/no-go pilot on one GPU (>= 24 GB; tested plan: 1x A100 40 GB or RTX 4090).
# Expected cost: ~1,800 deep contrast items x 6 conditions x 2 models = ~22k generations;
# prompts <= ~1.9k tokens, answers ~50-150 tokens. With vLLM: about 1-1.5 h per 7-8B model on an
# A100, 2-3 h on an RTX 4090. The run is resumable (JSONL keyed by model/condition/item).
set -euo pipefail
cd "$(dirname "$0")/.."

uv pip install -e ".[llm,analysis]"
huggingface-cli whoami >/dev/null || { echo "Run 'huggingface-cli login' (Llama 3.1 is gated)"; exit 1; }

# 1. data (deterministic: seeds are fixed in the code)
python scripts/convert_export.py --extension data/extension/core_extension.json \
    --extension data/extension/lexicon_stubs.json --out data/processed/fungramkb.json
fgkb bench --kb data/processed/fungramkb.json --out data/processed/fgkb_reason.jsonl --deep > results/bench_summary.json
python scripts/validate_offline.py --bench data/processed/fgkb_reason.jsonl --kb data/processed/fungramkb.json \
    --out results/validation.json --report docs/validation_report.md
sha256sum data/processed/fgkb_reason.jsonl | tee results/pilot_bench.sha256   # record in the preregistration

# 2. generations
fgkb run --config configs/pilot.yaml

# 3. preregistered analysis
python scripts/pilot_analysis.py --results results/pilot.jsonl --bench data/processed/fgkb_reason.jsonl \
    --out results/pilot_analysis.json --report docs/pilot_report.md
echo "Done: docs/pilot_report.md"
