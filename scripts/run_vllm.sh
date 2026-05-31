#!/usr/bin/env bash
# =============================================================
# vLLM 서버 실행 (setup_vllm.sh 를 먼저 돌려둔 상태에서)
#
# 실행:  bash scripts/run_vllm.sh
# 모델/포트 바꾸기:  MODEL=... PORT=... bash scripts/run_vllm.sh
# =============================================================
set -eo pipefail

# repo 루트의 .env 로드 (VLLM_API_KEY 등 환경변수)
ENV_FILE="$(cd "$(dirname "$0")/.." && pwd)/.env"
if [ -f "$ENV_FILE" ]; then
  echo "[.env 로드] $ENV_FILE"
  set -a; source "$ENV_FILE"; set +a
fi

CONDA_DIR="${CONDA_DIR:-$HOME/anaconda3}"
ENV_NAME="${ENV_NAME:-vllm}"
MODEL="${MODEL:-${VLLM_MODEL:-Qwen/Qwen2.5-7B-Instruct}}"
PORT="${PORT:-${VLLM_PORT:-8888}}"
HOST="${VLLM_HOST:-${VLLM_URL:-0.0.0.0}}"

source "$CONDA_DIR/etc/profile.d/conda.sh"
conda activate "$ENV_NAME"

GPU_UTIL="${VLLM_GPU_MEMORY_UTILIZATION:-0.90}"

# 같은 포트에 vLLM이 이미 떠 있으면 중복 기동 방지 (GPU OOM → Engine core failed)
if command -v ss >/dev/null 2>&1 && ss -tlnp 2>/dev/null | grep -q ":${PORT} "; then
  echo "⚠️  포트 ${PORT}에서 이미 vLLM이 실행 중입니다."
  echo "   확인: curl -s http://127.0.0.1:${PORT}/v1/models -H \"Authorization: Bearer \${VLLM_API_KEY}\""
  echo "   재시작: pkill -f 'vllm serve' ; sleep 2 ; bash scripts/run_vllm.sh"
  exit 1
fi
if pgrep -f "vllm serve" >/dev/null 2>&1; then
  echo "⚠️  다른 vLLM 프로세스가 GPU 메모리를 사용 중입니다 (nvidia-smi 확인)."
  echo "   종료 후 재시도: pkill -f 'vllm serve'"
  exit 1
fi

# flashinfer JIT: nvcc 없으면 PyTorch sampler 사용 (RunPod 기본 이미지에 nvcc 없음)
_NVCC="$(find "$CONDA_PREFIX/lib" -path '*/site-packages/nvidia/*/bin/nvcc' 2>/dev/null | head -1)"
if [ -n "$_NVCC" ]; then
  export CUDA_HOME="$(cd "$(dirname "$_NVCC")/.." && pwd)"
  export PATH="$(dirname "$_NVCC"):$PATH"
  echo "[CUDA] CUDA_HOME=$CUDA_HOME"
else
  export VLLM_USE_FLASHINFER_SAMPLER="${VLLM_USE_FLASHINFER_SAMPLER:-0}"
  echo "[CUDA] nvcc 없음 → VLLM_USE_FLASHINFER_SAMPLER=$VLLM_USE_FLASHINFER_SAMPLER"
fi

API_KEY_ARG=()
if [ -n "${VLLM_API_KEY:-}" ] && [ "${VLLM_API_KEY}" != "EMPTY" ]; then
  API_KEY_ARG=(--api-key "$VLLM_API_KEY")
fi

echo "vLLM 서빙: $MODEL  (바인드 $HOST:$PORT)"
vllm serve "$MODEL" \
  --host "$HOST" \
  --port "$PORT" \
  --max-model-len 8192 \
  --gpu-memory-utilization "$GPU_UTIL" \
  "${API_KEY_ARG[@]}"
