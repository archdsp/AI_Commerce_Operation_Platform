#!/usr/bin/env python3
"""토픽 관리 엔트리 — 생성 / 리셋(삭제+재생성) / 목록.

  python scripts/kafka_admin.py --list
  python scripts/kafka_admin.py --create
  python scripts/kafka_admin.py --reset     # 개발/데모 전용

로직은 src/edge_simulator/admin.py 에 있다.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from edge_simulator.admin import run_admin
from edge_simulator.config import KafkaConfig
from edge_simulator.logging_setup import setup_logging


def main() -> None:
    ap = argparse.ArgumentParser(description="Kafka/MSK 토픽 관리")
    ap.add_argument("--create", action="store_true", help="없는 토픽만 생성")
    ap.add_argument("--reset", action="store_true", help="삭제 후 재생성 (개발/데모 전용)")
    ap.add_argument("--list", action="store_true", help="토픽 목록")
    args = ap.parse_args()

    action = "reset" if args.reset else "create" if args.create else "list" if args.list else None
    if action is None:
        ap.print_help()
        return
    setup_logging("edge_simulator")
    asyncio.run(run_admin(KafkaConfig.from_env(), action))


if __name__ == "__main__":
    main()
