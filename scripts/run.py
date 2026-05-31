#!/usr/bin/env python3
"""점포 시뮬레이터 엔트리 — data/edges 샤드를 AWS MSK로 "실시간처럼" 발행.

먼저 `python scripts/prepare_edges.py` 로 샤드를 생성해야 한다.

  python scripts/run.py                                # 전체 발행(TAF 가속)
  python scripts/run.py --dry-run --max-events 20000   # 브로커 없이 점검
  python scripts/run.py --rate 20000 --scale 50        # 대용량(점포 ×50, 2만 msg/s)
  python scripts/run.py --shard-count 3 --shard-index 0  # 다중 프로듀서 분산

로직은 src/edge_simulator/ 모듈에 있다. 본 파일은 CLI 진입점일 뿐이다.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from edge_simulator.config import KafkaConfig, edges_dir
from edge_simulator.logging_setup import setup_logging
from edge_simulator.producer import RunOptions, run


def main() -> None:
    ap = argparse.ArgumentParser(description="Olist 점포 시뮬레이터 → MSK")
    ap.add_argument("--dry-run", action="store_true", help="브로커 없이 카운트만")
    ap.add_argument("--events", choices=["all", "orders", "reviews"], default="all")
    speed = ap.add_mutually_exclusive_group()
    speed.add_argument("--taf", type=float, default=8760.0, help="시간가속계수 (기본 8760)")
    speed.add_argument("--rate", type=float, default=0.0, help="초당 고정 발행(전역)")
    ap.add_argument("--scale", type=int, default=1, help="점포 합성복제 배수")
    ap.add_argument("--shard-index", type=int, default=0)
    ap.add_argument("--shard-count", type=int, default=1)
    ap.add_argument("--max-events", type=int, default=0)
    ap.add_argument("--max-sleep", type=float, default=1.0)
    ap.add_argument("--loop", action="store_true", help="끝나면 처음부터 재생(지속 부하)")
    ap.add_argument("--edges-dir", type=Path, default=None)
    args = ap.parse_args()

    setup_logging("edge_simulator")
    cfg = KafkaConfig.from_env()
    opts = RunOptions(
        taf=args.taf, rate=args.rate, scale=args.scale,
        shard_index=args.shard_index, shard_count=args.shard_count,
        max_events=args.max_events, max_sleep=args.max_sleep,
        loop=args.loop, dry_run=args.dry_run, events=args.events,
    )
    asyncio.run(run(cfg, args.edges_dir or edges_dir(), opts))


if __name__ == "__main__":
    main()
