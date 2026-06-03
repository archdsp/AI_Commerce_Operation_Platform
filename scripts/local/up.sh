#!/usr/bin/env bash
# ── 로컬 전 구간 원커맨드 기동 (macOS · Linux · WSL Ubuntu) ─────────────────
# Docker 인프라(MySQL·Redpanda·Qdrant) + Ollama로 데이터→스트리밍→집계→RAG→게이트웨이까지.
# AWS 불필요. 멱등 — 다시 실행해도 안전(샘플은 결정론적).
#   scripts/local/up.sh
# 사전: Docker Desktop(또는 docker), Ollama, Python deps(pip install -r requirements.txt). 상세 docs/LOCAL.md
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export ENV_FILE=".env.local"
PY="${PYTHON:-python3}"
COMPOSE_FILE="docker-compose.local.yml"

# docker compose v2(plugin) / v1(docker-compose) 자동 선택
if docker compose version >/dev/null 2>&1; then DC="docker compose"; else DC="docker-compose"; fi
compose() { $DC -f "$COMPOSE_FILE" "$@"; }

wait_health() {  # 컨테이너 healthcheck=healthy 대기
  local name="$1" t="${2:-120}" i=0
  printf "   %s health 대기" "$name"
  until [ "$(docker inspect -f '{{.State.Health.Status}}' "$name" 2>/dev/null || echo none)" = "healthy" ]; do
    i=$((i+2)); printf "."; [ "$i" -ge "$t" ] && { echo " ✗ timeout"; docker logs --tail 25 "$name" || true; exit 1; }
    sleep 2
  done; echo " ✓"
}
wait_http() {    # HTTP 200 대기
  local url="$1" t="${2:-60}" i=0
  printf "   %s 대기" "$url"
  until curl -fs -m 2 "$url" >/dev/null 2>&1; do
    i=$((i+2)); printf "."; [ "$i" -ge "$t" ] && { echo " ✗ timeout"; exit 1; }
    sleep 2
  done; echo " ✓"
}

echo "▶ 0/8 사전 점검"
command -v docker  >/dev/null || { echo "✗ docker 필요 — Docker Desktop 설치/실행"; exit 1; }
command -v ollama  >/dev/null || { echo "✗ ollama 필요 — https://ollama.com"; exit 1; }
[ -f .env.local ] || { cp .env.local.example .env.local; echo "   .env.local 생성(예시 복사)"; }
MODEL="$(grep -E '^VLLM_MODEL=' .env.local | cut -d= -f2- | tr -d ' ')"; MODEL="${MODEL:-qwen2.5:7b}"

echo "▶ 1/8 인프라 기동 (MySQL · Redpanda · Qdrant)"
compose up -d
wait_health acop-mysql 150
wait_health acop-redpanda 90
wait_http http://localhost:6333/readyz 60

echo "▶ 2/8 Ollama 모델 준비: $MODEL"
curl -fs -m 3 http://localhost:11434/api/tags >/dev/null 2>&1 || { echo "✗ Ollama 서버 미응답 — 'ollama serve' 실행 후 재시도"; exit 1; }
ollama list | grep -q "$MODEL" || ollama pull "$MODEL"

echo "▶ 3/8 MySQL 스키마 + 샘플 적재 + api_keys 시드"
"$PY" scripts/setup_mysql.py

echo "▶ 4/8 엣지 샤드 생성 (샘플 데이터)"
"$PY" scripts/prepare_edges.py

echo "▶ 5/8 Kafka 토픽 생성"
"$PY" scripts/kafka_admin.py --create

echo "▶ 6/8 발행 → 감성/VOC 분석 → 카테고리 집계"
"$PY" scripts/run.py --rate 4000 --duration 120
"$PY" scripts/review_analyzer.py  --duration 30
"$PY" scripts/metric_aggregator.py --duration 30

echo "▶ 7/8 RAG 적재 (리뷰 임베딩 → Qdrant)"
"$PY" scripts/reload_qdrant.py --limit 6000

echo "▶ 8/8 게이트웨이 기동"
scripts/local/serve.sh start

cat <<EOF

✅ 로컬 기동 완료
   • 웹 UI    : http://localhost:8000
   • 데모 키  : oy_demo_md_key  (voc: oy_demo_voc_key · ops: oy_demo_ops_key)
   • 예시:
     curl -s -X POST http://localhost:8000/v1/chat \\
       -H 'Content-Type: application/json' -H 'X-API-Key: oy_demo_md_key' \\
       -d '{"query":"판매량이 가장 많은 카테고리는?"}'
   • 종료: scripts/local/down.sh
EOF
