#!/usr/bin/env bash
# 게이트웨이 기동/종료/상태 — macOS · Linux · WSL Ubuntu 공통.
# (기존 serve_demo.sh의 Linux 전용 ss/setsid 미사용 → PID파일 + health curl)
#
#   scripts/local/serve.sh start|stop|restart|status
#
# 환경변수: GW_PORT(기본 8000) · ENV_FILE(기본 .env.local)
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PORT="${GW_PORT:-8000}"
DIR="$ROOT/.local"
LOG="${GW_LOG:-$DIR/gateway.log}"
PIDFILE="$DIR/gateway.pid"
export ENV_FILE="${ENV_FILE:-.env.local}"
export GW_PORT="$PORT"
mkdir -p "$DIR"

healthy() { curl -fs -m 2 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; }
PY="${PYTHON:-python3}"

start() {
  if healthy; then echo "✓ 이미 실행 중 · http://localhost:$PORT"; return 0; fi
  cd "$ROOT" || exit 1
  nohup "$PY" scripts/run_gateway.py >"$LOG" 2>&1 < /dev/null &
  echo $! > "$PIDFILE"
  for _ in $(seq 1 40); do
    healthy && { echo "✓ 기동 완료 · http://localhost:$PORT · log=$LOG"; return 0; }
    sleep 1
  done
  echo "✗ 기동 실패(health 미응답) — 로그:"; tail -30 "$LOG" 2>/dev/null; return 1
}

stop() {
  if [ -f "$PIDFILE" ] && kill "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "종료 pid $(cat "$PIDFILE")"
  else
    echo ":$PORT PID 파일 없음/이미 종료"
  fi
  rm -f "$PIDFILE"
}

case "${1:-start}" in
  start)   start ;;
  stop)    stop ;;
  restart) stop; sleep 1; start ;;
  status)  healthy && echo "RUNNING :$PORT" || echo "NOT running :$PORT" ;;
  *) echo "usage: $0 {start|stop|restart|status}"; exit 1 ;;
esac
