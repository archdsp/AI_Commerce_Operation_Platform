#!/usr/bin/env bash
# AI Commerce Ops — 데모 웹 게이트웨이 상시 기동 관리.
# 세션/SSH가 끊겨도 살아있도록 setsid+nohup으로 완전 분리 실행한다.
#
#   scripts/serve_demo.sh start     # 기동(이미 떠 있으면 그대로)
#   scripts/serve_demo.sh stop      # 종료
#   scripts/serve_demo.sh restart   # 재기동
#   scripts/serve_demo.sh status    # 상태
#
# 환경변수: GW_PORT(기본 8000) · GW_LOG(기본 ~/gw_demo.log) · GW_PID(기본 ~/gw_demo.pid)
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${GW_PORT:-8000}"
LOG="${GW_LOG:-$HOME/gw_demo.log}"
PIDFILE="${GW_PID:-$HOME/gw_demo.pid}"

port_pid() { ss -ltnp 2>/dev/null | grep ":$PORT " | grep -oP 'pid=\K[0-9]+' | head -1; }
healthy()  { curl -fs -m 2 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; }

start() {
  if healthy; then echo "이미 실행 중 (health OK) :$PORT (pid $(port_pid))"; return 0; fi
  cd "$ROOT" || exit 1
  setsid nohup python3 scripts/run_gateway.py >"$LOG" 2>&1 < /dev/null &
  echo $! > "$PIDFILE"
  for _ in $(seq 1 30); do
    healthy && { echo "기동 완료 · health OK · pid=$(port_pid) · log=$LOG"; return 0; }
    sleep 1
  done
  echo "기동 실패(health 미응답) — 로그 확인: $LOG"; tail -20 "$LOG" 2>/dev/null; return 1
}

stop() {
  local p; p="$(port_pid)"
  if [ -n "$p" ]; then kill "$p" 2>/dev/null && echo "종료 pid $p"; else echo ":$PORT 에 실행 중인 프로세스 없음"; fi
  rm -f "$PIDFILE"
}

status() {
  if healthy; then echo "RUNNING :$PORT (pid $(port_pid)) · log=$LOG"; else echo "NOT running :$PORT"; fi
}

case "${1:-start}" in
  start)   start ;;
  stop)    stop ;;
  restart) stop; sleep 1; start ;;
  status)  status ;;
  *) echo "usage: $0 {start|stop|restart|status}"; exit 1 ;;
esac
