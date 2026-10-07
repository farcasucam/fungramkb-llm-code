#!/usr/bin/env bash
# Run ON the DGX Spark: start two vLLM OpenAI-compatible servers (bf16) for the pilot.
#   Qwen/Qwen2.5-7B-Instruct          -> port 8000
#   meta-llama/Llama-3.1-8B-Instruct  -> port 8001   (gated: needs HF_TOKEN with access granted)
#
#   export HF_TOKEN=hf_...            # https://huggingface.co/settings/tokens
#   bash spark_vllm_up.sh             # first start downloads ~15 + ~16 GB of weights
#
# Image: NVIDIA's vLLM container for ARM64/Blackwell. Check the newest tag at
# https://catalog.ngc.nvidia.com/orgs/nvidia/containers/vllm and override with VLLM_IMAGE=...
set -euo pipefail
IMAGE="${VLLM_IMAGE:-nvcr.io/nvidia/vllm:25.09-py3}"
: "${HF_TOKEN:?export HF_TOKEN=hf_... first (Llama 3.1 is gated on Hugging Face)}"

# Ollama keeps the GPU memory of loaded models; free it (the container is not removed)
docker stop ollama >/dev/null 2>&1 && echo "ollama container stopped (restart later with: docker start ollama)" || true

start() {  # container-name host-port hf-model
  docker rm -f "$1" >/dev/null 2>&1 || true
  docker run -d --name "$1" --gpus all --ipc=host --restart unless-stopped -p "$2":8000 \
    -e HF_TOKEN -v "$HOME/.cache/huggingface:/root/.cache/huggingface" "$IMAGE" \
    vllm serve "$3" --host 0.0.0.0 --port 8000 --dtype bfloat16 --max-model-len 8192 \
      --gpu-memory-utilization 0.40 --seed 0 >/dev/null
  echo "started $1 ($3) on port $2"
}
start fgkb-qwen 8000 Qwen/Qwen2.5-7B-Instruct
start fgkb-llama 8001 meta-llama/Llama-3.1-8B-Instruct

for port in 8000 8001; do
  echo -n "waiting for port $port (weights download + load, several minutes the first time) "
  until curl -sf "localhost:$port/v1/models" >/dev/null; do
    sleep 15; echo -n "."
    if ! docker ps --format '{{.Names}}' | grep -q "fgkb-"; then echo; echo "a container stopped: docker logs fgkb-qwen / fgkb-llama"; exit 1; fi
  done
  echo " ready"
done
echo "Both servers ready. Run the pilot from the PC with: scripts\\run_pilot_windows.ps1 -Mode vllm"
