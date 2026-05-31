#!/usr/bin/env python3
"""Metric Aggregator 엔트리 — review_analyzed → daily_category_metrics(RDS MySQL) + metric_updated.

  python scripts/metric_aggregator.py --duration 60

로직은 src/consumers/metric_aggregator.py. 로그: /workspace/app_logs/metric_aggregator/.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from consumers.metric_aggregator import AggregatorOptions, run
from edge_simulator.config import KafkaConfig
from edge_simulator.logging_setup import setup_logging


def main() -> None:
    ap = argparse.ArgumentParser(description="Metric Aggregator (review_analyzed → daily_category_metrics)")
    ap.add_argument("--duration", type=float, default=0.0, help="N초 후 자동 종료(0=무제한). 비용 제어")
    ap.add_argument("--batch", type=int, default=1000)
    args = ap.parse_args()

    setup_logging("metric_aggregator")
    asyncio.run(run(KafkaConfig.from_env(), AggregatorOptions(duration=args.duration, batch=args.batch)))


if __name__ == "__main__":
    main()
