#!/usr/bin/env python3
"""Multi-Agent 질의 엔트리 — NL 질문 → Router → Text-to-SQL(MySQL) + RAG(Qdrant) → vLLM 답변.

  python scripts/agent_query.py "카테고리별 매출 순위 알려줘"
  python scripts/agent_query.py "배송 관련 부정 리뷰 알려줘" --agent voc

로직은 src/agents/. 로그: /workspace/app_logs/agents/.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from agents.graph import answer_query
from edge_simulator.logging_setup import setup_logging


def main() -> None:
    ap = argparse.ArgumentParser(description="Multi-Agent(LangGraph) 질의")
    ap.add_argument("query")
    ap.add_argument("--agent", choices=["md", "voc", "insight"], default=None, help="라우터 건너뛰고 지정")
    ap.add_argument("--sim-today", default="2026-05-31")
    args = ap.parse_args()

    setup_logging("agents")
    r = answer_query(args.query, args.agent, args.sim_today)
    print(f"\n[agent] {r.get('agent_type')}")
    if r.get("sql"):
        print(f"[sql] {r['sql']}")
    print(f"[rows] {len(r.get('rows', []))} | [rag] {len(r.get('rag', []))}")
    if r.get("note"):
        print(f"[note] {r['note']}")
    print("\n[answer]\n" + (r.get("answer") or ""))


if __name__ == "__main__":
    main()
