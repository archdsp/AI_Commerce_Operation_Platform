#!/usr/bin/env python3
"""발행 도착 검증 엔트리 — 토픽을 earliest로 소비해 건수/샘플 확인.

  python scripts/consume_check.py --sample 3

로직은 src/edge_simulator/verify.py 에 있다.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from edge_simulator.config import KafkaConfig
from edge_simulator.logging_setup import setup_logging
from edge_simulator.verify import consume_check


def main() -> None:
    ap = argparse.ArgumentParser(description="발행 도착 검증(소비)")
    ap.add_argument("--sample", type=int, default=0, help="토픽별 샘플 출력 건수")
    ap.add_argument("--budget", type=float, default=20.0, help="최대 소비 시간(초)")
    args = ap.parse_args()

    setup_logging("edge_simulator")
    asyncio.run(consume_check(KafkaConfig.from_env(), args.sample, args.budget))


if __name__ == "__main__":
    main()
