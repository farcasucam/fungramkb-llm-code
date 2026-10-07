#!/usr/bin/env bash
# Run ON the DGX Spark: serve the W3 paraphrasing model (prompt-robustness wordings) on port 8003.
# The paraphraser must not be one of the evaluated families (Qwen, Llama, OLMo). Default:
# Mistral-Small-3.2-24B-Instruct-2506 (Apache-2.0, strong in Spanish). ~48 GB in bf16, so the other
# fgkb-* containers are stopped first (restart them later with: docker start fgkb-qwen fgkb-llama fgkb-olmo).
#
#   bash spark_paraphraser_up.sh
#   PARA_MODEL=microsoft/phi-4 bash spark_paraphraser_up.sh      # fallback if the Mistral repo needs approval
#   export HF_TOKEN=hf_...   # only if the Hugging Face repo is gated for your account
set -euo pipefail
IMAGE="${VLLM_IMAGE:-nvcr.io/nvidia/vllm:26.09-py3}"
MODEL="${PARA_MODEL:-mistralai/Mistral-Small-3.2-24B-Instruct-2506}"
PORT=8003
EXTRA=()
case "$MODEL" in mistralai/*) EXTRA=(--tokenizer-mode mistral --config-format mistral --load-format mistral);; esac

for c in fgkb-qwen fgkb-llama fgkb-olmo; do
  docker stop "$c" >/dev/null 2>&1 && echo "$c stopped (restart later with: docker start $c)" || true
done
docker rm -f fgkb-para >/dev/null 2>&1 || true
docker run -d --name fgkb-para --gpus all --ipc=host -p "$PORT":8000 ${HF_TOKEN:+-e HF_TOKEN} \
  -v "$HOME/.cache/huggingface:/root/.cache/huggingface" "$IMAGE" \
  vllm serve "$MODEL" --host 0.0.0.0 --port 8000 --dtype bfloat16 --max-model-len 4096 \
    --gpu-memory-utilization 0.70 --seed 0 "${EXTRA[@]}" >/dev/null
echo "started fgkb-para ($MODEL) on port $PORT"
echo -n "waiting for port $PORT (download ~48 GB the first time) "
until curl -sf "localhost:$PORT/v1/models" >/dev/null; do
  sleep 15; echo -n "."
  if ! docker ps --format '{{.Names}}' | grep -q "^fgkb-para$"; then
    echo; echo "the container stopped; last log lines:"; docker logs --tail 30 fgkb-para; exit 1
  fi
done
echo " ready"; curl -s "localhost:$PORT/v1/models"; echo
