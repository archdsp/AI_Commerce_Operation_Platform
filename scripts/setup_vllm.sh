#!/usr/bin/env bash
# =============================================================
# RunPod vLLM 환경 구성 스크립트
#   1) Anaconda3 설치 (없으면)
#   2) conda 환경 'vllm' 생성 (Python 3.11)
#   3) 드라이버 CUDA 버전에 맞는 vLLM + PyTorch 설치
#
# 실행:  bash scripts/setup_vllm.sh
#
# 가벼운 대안: Anaconda(~600MB) 대신 Miniconda를 쓰려면 ANACONDA_URL을
#   https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
# 로 바꿔서 실행하면 된다.
# =============================================================
set -eo pipefail   # conda activate 호환 위해 -u 는 빼둠

CONDA_DIR="${CONDA_DIR:-$HOME/anaconda3}"
ENV_NAME="${ENV_NAME:-vllm}"
PY_VERSION="${PY_VERSION:-3.11}"
VLLM_VERSION="${VLLM_VERSION:-0.22.0}"
ANACONDA_URL="${ANACONDA_URL:-https://repo.anaconda.com/archive/Anaconda3-2024.10-1-Linux-x86_64.sh}"

_arch="$(uname -m)"
case "$_arch" in
  x86_64) VLLM_ARCH=x86_64; VLLM_MANYLINUX=2_28 ;;
  aarch64) VLLM_ARCH=aarch64; VLLM_MANYLINUX=2_28 ;;
  *) echo "지원하지 않는 CPU 아키텍처: $_arch" >&2; exit 1 ;;
esac

echo "[1/3] Anaconda3 확인/설치 -> $CONDA_DIR"
if [ ! -d "$CONDA_DIR" ]; then
  cd /tmp
  if command -v wget >/dev/null 2>&1; then
    wget -qO anaconda.sh "$ANACONDA_URL"
  else
    curl -fsSL "$ANACONDA_URL" -o anaconda.sh
  fi
  bash anaconda.sh -b -p "$CONDA_DIR"
  rm -f anaconda.sh
else
  echo "    이미 설치됨 (건너뜀)"
fi

source "$CONDA_DIR/etc/profile.d/conda.sh"
conda init bash >/dev/null 2>&1 || true

echo "[2/3] conda 환경 '$ENV_NAME' (python $PY_VERSION)"
if ! conda env list | grep -qE "^\s*${ENV_NAME}\s"; then
  conda create -y -n "$ENV_NAME" python="$PY_VERSION"
else
  echo "    이미 있음 (건너뜀)"
fi
conda activate "$ENV_NAME"

echo "[3/3] vLLM 설치 (torch+CUDA 포함, 수 분 소요)"
python -m pip install --upgrade pip

# PyPI 기본 vLLM wheel은 cu13 → driver 12.x에서 torch CUDA 초기화 실패
# GitHub release wheel + PyTorch cu128/cu129 조합 사용
TORCH_BACKEND="${TORCH_BACKEND:-}"
VLLM_CUDA_TAG="${VLLM_CUDA_TAG:-}"
if [ -z "$TORCH_BACKEND" ] && command -v nvidia-smi >/dev/null 2>&1; then
  DRIVER_CUDA="$(nvidia-smi 2>/dev/null | sed -n 's/.*CUDA Version: \([0-9.]*\).*/\1/p' | head -1)"
  case "$DRIVER_CUDA" in
    13.*)
      TORCH_BACKEND=cu130
      VLLM_CUDA_TAG=cu130
      ;;
    12.9|12.8)
      TORCH_BACKEND=cu128
      VLLM_CUDA_TAG=cu129   # v0.22.0 release: cu129 wheel + cu128 torch
      ;;
    12.*)
      TORCH_BACKEND=cu124
      VLLM_CUDA_TAG=cu129
      ;;
    *)
      TORCH_BACKEND=cu128
      VLLM_CUDA_TAG=cu129
      ;;
  esac
  echo "    nvidia-smi CUDA $DRIVER_CUDA → torch $TORCH_BACKEND, vllm +$VLLM_CUDA_TAG"
else
  TORCH_BACKEND="${TORCH_BACKEND:-cu128}"
  VLLM_CUDA_TAG="${VLLM_CUDA_TAG:-cu129}"
fi

python -m pip uninstall -y vllm torch torchvision torchaudio 2>/dev/null || true

if [ "$VLLM_CUDA_TAG" = "cu130" ]; then
  python -m pip install --no-cache-dir "vllm==${VLLM_VERSION}" openai \
    --extra-index-url "https://download.pytorch.org/whl/${TORCH_BACKEND}"
else
  VLLM_WHEEL="https://github.com/vllm-project/vllm/releases/download/v${VLLM_VERSION}/vllm-${VLLM_VERSION}+${VLLM_CUDA_TAG}-cp38-abi3-manylinux_${VLLM_MANYLINUX}_${VLLM_ARCH}.whl"
  echo "    vLLM wheel: $VLLM_WHEEL"
  python -m pip install --no-cache-dir torch torchvision torchaudio \
    --index-url "https://download.pytorch.org/whl/${TORCH_BACKEND}"
  python -m pip install --no-cache-dir "$VLLM_WHEEL" openai
fi

echo ""
echo "GPU / PyTorch 확인:"
python - <<'PY'
import torch
print(f"  torch {torch.__version__}  cuda {torch.version.cuda}  available={torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"  device: {torch.cuda.get_device_name(0)}")
PY

echo ""
echo "✅ 완료!"
echo "   1) GPU 인식 확인:  nvidia-smi"
echo "   2) 서버 실행:      bash scripts/run_vllm.sh"
echo "   3) 테스트:         curl -s http://127.0.0.1:\${VLLM_PORT:-8888}/v1/models -H \"Authorization: Bearer \$VLLM_API_KEY\""
