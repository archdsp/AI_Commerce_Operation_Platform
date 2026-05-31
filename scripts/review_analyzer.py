#!/usr/bin/env python3
"""Review Analyzer 엔트리 — review_created 소비 → 감성/VOC → review_analysis.

  python scripts/review_analyzer.py --duration 60          # 1분만(비용 제어)
  python scripts/review_analyzer.py --analyzer llm         # RunPod LLM 사용(미설정 시 휴리스틱 폴백)
  python scripts/review_analyzer.py --no-db                # DB 쓰기 생략(로그만)

로직은 src/consumers/review_analyzer.py 에 있다. 로그: /workspace/app_logs/review_analyzer/.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from consumers.review_analyzer import ConsumerOptions, run
from edge_simulator.config import KafkaConfig
from edge_simulator.logging_setup import setup_logging


def main() -> None:
    ap = argparse.ArgumentParser(description="Review Analyzer (review_created → review_analysis)")
    ap.add_argument("--analyzer", choices=["heuristic", "llm"], default="heuristic")
    ap.add_argument("--duration", type=float, default=0.0, help="N초 후 자동 종료(0=무제한). 비용 제어")
    ap.add_argument("--batch", type=int, default=500)
    ap.add_argument("--no-db", action="store_true", help="DB 쓰기 생략(로그만)")
    args = ap.parse_args()

    setup_logging("review_analyzer")
    opts = ConsumerOptions(analyzer=args.analyzer, duration=args.duration,
                           batch=args.batch, use_db=not args.no_db)
    asyncio.run(run(KafkaConfig.from_env(), opts))


if __name__ == "__main__":
    main()
