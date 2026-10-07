#!/usr/bin/env bash
# Run ON the DGX Spark: serve the three models of the main study with ONE vLLM image
# (docs/analysis_plan.md, section 3), all at the same time.
#   Qwen/Qwen2.5-7B-Instruct          -> port 8000
#   meta-llama/Llama-3.1-8B-Instruct  -> port 8001   (gated: needs HF_TOKEN)
#   allenai/Olmo-3-7B-Instruct        -> port 8002
#
#   export HF_TOKEN=hf_...
#   bash spark_main_up.sh
#
# Stops every other fgkb-* container (pilot servers, the Mistral paraphraser) and Ollama to free the
# unified memory: 3 x 0.22 = 0.66 of the GPU memory (NVIDIA advises <= 0.7 on DGX Spark).
set -euo pipefail
IMAGE="${VLLM_IMAGE:-nvcr.io/nvidia/vllm:26.09-py3}"
MEM="${GPU_MEM:-0.22}"
: "${HF_TOKEN:?export HF_TOKEN=hf_... first (Llama 3.1 is gated on Hugging Face)}"

for c in $(docker ps -a --format '{{.Names}}' | grep '^fgkb-' || true); do
  docker rm -f "$c" >/dev/null && echo "removed $c"
done
docker stop ollama >/dev/null 2>&1 && echo "ollama stopped" || true

docker pull -q "$IMAGE" >/dev/null
DIGEST=$(docker image inspect --format '{{index .RepoDigests 0}}' "$IMAGE")
echo "image: $DIGEST"

start() {  # container-name host-port hf-model
  docker run -d --name "$1" --gpus all --ipc=host --restart unless-stopped -p "$2":8000 \
    -e HF_TOKEN -v "$HOME/.cache/huggingface:/root/.cache/huggingface" "$IMAGE" \
    vllm serve "$3" --host 0.0.0.0 --port 8000 --dtype bfloat16 --max-model-len 8192 \
      --gpu-memory-utilization "$MEM" --seed 0 >/dev/null
  echo "started $1 ($3) on port $2"
}
# one at a time: loading three models at once can exceed the memory during profiling
for spec in "fgkb-qwen 8000 Qwen/Qwen2.5-7B-Instruct" "fgkb-llama 8001 meta-llama/Llama-3.1-8B-Instruct" \
            "fgkb-olmo 8002 allenai/Olmo-3-7B-Instruct"; do
  set -- $spec
  start "$1" "$2" "$3"
  echo -n "waiting for port $2 "
  until curl -sf "localhost:$2/v1/models" >/dev/null; do
    sleep 15; echo -n "."
    if ! docker ps --format '{{.Names}}' | grep -q "^$1$"; then
      echo; echo "$1 stopped; last log lines:"; docker logs --tail 30 "$1"; exit 1
    fi
  done
  echo " ready ($(curl -s "localhost:$2/version"))"
done

{ echo "image=$DIGEST"; date -Iseconds; for p in 8000 8001 8002; do curl -s "localhost:$p/v1/models"; echo; done; } \
  > "$HOME/fgkb_main_servers.txt"
echo "Servers ready; details in ~/fgkb_main_servers.txt"
echo "From the PC: powershell -ExecutionPolicy Bypass -File scripts\\run_main_windows.ps1"
