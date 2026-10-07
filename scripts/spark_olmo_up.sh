#!/usr/bin/env bash
# Run ON the DGX Spark: start allenai/Olmo-3-7B-Instruct (bf16) with vLLM on port 8002.
# Third model family of the pilot: fully open weights AND training data (Dolma 3 / Dolci), which
# enables the pretraining-contamination check for FunGramKB.
#
#   bash spark_olmo_up.sh                      # stops fgkb-qwen / fgkb-llama to give Olmo the GPU memory
#   KEEP_OTHERS=1 bash spark_olmo_up.sh        # keep them running (Olmo gets 0.25 of the memory)
#   VLLM_IMAGE=nvcr.io/nvidia/vllm:<tag> bash spark_olmo_up.sh
#
# Olmo 3 needs transformers >= 4.57 and a vLLM build that registers Olmo3ForCausalLM. The script checks
# the image first; if the check fails, pick a newer tag at
# https://catalog.ngc.nvidia.com/orgs/nvidia/containers/vllm and pass it as VLLM_IMAGE.
# The model is not gated: no HF_TOKEN needed.
set -euo pipefail
IMAGE="${VLLM_IMAGE:-nvcr.io/nvidia/vllm:25.09-py3}"
MODEL="${OLMO_MODEL:-allenai/Olmo-3-7B-Instruct}"
PORT=8002

echo "checking that $IMAGE supports Olmo 3 ..."
if ! docker run --rm "$IMAGE" python3 -c "
import transformers, vllm
from vllm import ModelRegistry
ok = 'Olmo3ForCausalLM' in ModelRegistry.get_supported_archs()
print(f'vllm {vllm.__version__}, transformers {transformers.__version__}, Olmo3 supported: {ok}')
raise SystemExit(0 if ok else 1)
"; then
  echo "This image cannot serve Olmo 3. Use a newer NGC vLLM tag, e.g.:"
  echo "  VLLM_IMAGE=nvcr.io/nvidia/vllm:<newer-tag>-py3 bash spark_olmo_up.sh"
  echo "(or, as a fallback, OLMO_MODEL=allenai/OLMo-2-1124-7B-Instruct bash spark_olmo_up.sh)"
  exit 1
fi

if [ "${KEEP_OTHERS:-0}" = "1" ]; then
  MEM=0.25
else
  MEM=0.80
  for c in fgkb-qwen fgkb-llama; do
    docker stop "$c" >/dev/null 2>&1 && echo "$c stopped (restart later with: docker start $c)" || true
  done
fi
docker stop ollama >/dev/null 2>&1 || true

docker rm -f fgkb-olmo >/dev/null 2>&1 || true
docker run -d --name fgkb-olmo --gpus all --ipc=host --restart unless-stopped -p "$PORT":8000 \
  -v "$HOME/.cache/huggingface:/root/.cache/huggingface" "$IMAGE" \
  vllm serve "$MODEL" --host 0.0.0.0 --port 8000 --dtype bfloat16 --max-model-len 8192 \
    --gpu-memory-utilization "$MEM" --seed 0 >/dev/null
echo "started fgkb-olmo ($MODEL) on port $PORT, gpu-memory-utilization $MEM"

echo -n "waiting for port $PORT (weights download ~15 GB + load, several minutes the first time) "
until curl -sf "localhost:$PORT/v1/models" >/dev/null; do
  sleep 15; echo -n "."
  if ! docker ps --format '{{.Names}}' | grep -q "^fgkb-olmo$"; then
    echo; echo "the container stopped; last log lines:"; docker logs --tail 30 fgkb-olmo; exit 1
  fi
done
echo " ready"
curl -s "localhost:$PORT/v1/models"; echo
echo "Run from the PC: fgkb run --config configs\\pilot_spark_olmo.yaml"
