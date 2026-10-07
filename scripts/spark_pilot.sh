#!/usr/bin/env bash
# Go/no-go pilot on the NVIDIA DGX Spark (DGX OS, ARM64, GB10, 128 GB unified memory).
#
#   scripts/spark_pilot.sh ollama   # Ollama already running on the Spark (default)
#   scripts/spark_pilot.sh vllm     # vLLM containers from NGC (bf16, grammar-constrained N1)
#
# Expected time (deep contrast subset, ~1,900 items x 6 conditions per model):
#   Ollama fp16, OLLAMA_NUM_PARALLEL=8 : ~3-5 h per model   |   vLLM bf16 : < 2 h per model
# The run is resumable: re-launch the same command after an interruption.
set -euo pipefail
cd "$(dirname "$0")/.."
MODE="${1:-ollama}"

# 1. Python environment (client side only: no torch needed for the Ollama / vLLM-server routes)
if [ ! -d .venv ]; then python3 -m venv .venv; fi
. .venv/bin/activate
pip install -q --upgrade pip
pip install -q -e ".[remote,analysis]"

# 2. Data: copied from the project folder; regenerated only if missing (needs data/raw)
if [ ! -s data/processed/fgkb_reason.jsonl ]; then
  python scripts/convert_export.py --extension data/extension/core_extension.json \
      --extension data/extension/lexicon_stubs.json --out data/processed/fungramkb.json
  fgkb bench --kb data/processed/fungramkb.json --out data/processed/fgkb_reason.jsonl --deep > results/bench_summary.json
fi
mkdir -p results
sha256sum data/processed/fungramkb.json data/processed/fgkb_reason.jsonl | tee results/pilot_inputs.sha256

if [ "$MODE" = "ollama" ]; then
  OLLAMA="${OLLAMA_URL:-http://localhost:11434}"
  curl -sf "$OLLAMA/api/version" >/dev/null || { echo "Ollama not reachable at $OLLAMA"; exit 1; }
  echo "Tip: start Ollama with OLLAMA_NUM_PARALLEL=8 for ~5x throughput."
  python scripts/ollama_pull.py "$OLLAMA" qwen2.5:7b-instruct-fp16 llama3.1:8b-instruct-fp16
  CONFIG=configs/pilot_spark.yaml
  OUT=results/pilot_spark.jsonl
else
  # vLLM from NGC (ARM64 + Blackwell build). Check the current tag at catalog.ngc.nvidia.com (vllm).
  IMAGE="${VLLM_IMAGE:-nvcr.io/nvidia/vllm:25.09-py3}"
  : "${HF_TOKEN:?export HF_TOKEN=... (Llama 3.1 is gated on Hugging Face)}"
  start() {  # name port hf_id
    docker rm -f "$1" >/dev/null 2>&1 || true
    docker run -d --name "$1" --gpus all --ipc=host -p "$2":8000 -e HF_TOKEN \
      -v "$HOME/.cache/huggingface:/root/.cache/huggingface" "$IMAGE" \
      vllm serve "$3" --dtype bfloat16 --max-model-len 8192 --gpu-memory-utilization 0.35 --seed 0 >/dev/null
    echo -n "waiting for $3 on :$2 "; until curl -sf "localhost:$2/v1/models" >/dev/null; do sleep 10; echo -n .; done; echo " ok"
  }
  start fgkb-qwen 8000 Qwen/Qwen2.5-7B-Instruct
  start fgkb-llama 8001 meta-llama/Llama-3.1-8B-Instruct
  CONFIG=configs/pilot_spark_vllm.yaml
  OUT=results/pilot_spark_vllm.jsonl
fi

# 3. Generations (resumable) and preregistered analysis
fgkb run --config "$CONFIG"
python scripts/pilot_analysis.py --results "$OUT" --bench data/processed/fgkb_reason.jsonl \
    --out "${OUT%.jsonl}_analysis.json" --report docs/pilot_report.md
echo "Done: docs/pilot_report.md"
