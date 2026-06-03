#!/usr/bin/env bash
# 로컬 스택 종료 (macOS · Linux · WSL Ubuntu).
#   scripts/local/down.sh           # 게이트웨이 + 컨테이너 정지(데이터 볼륨 보존)
#   scripts/local/down.sh --purge   # 볼륨까지 삭제(완전 초기화)
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
if docker compose version >/dev/null 2>&1; then DC="docker compose"; else DC="docker-compose"; fi

scripts/local/serve.sh stop || true

if [ "${1:-}" = "--purge" ]; then
  echo "컨테이너 + 볼륨 삭제(완전 초기화)"
  $DC -f docker-compose.local.yml down -v
else
  echo "컨테이너 정지(볼륨 보존)"
  $DC -f docker-compose.local.yml down
fi
echo "✓ 종료"
