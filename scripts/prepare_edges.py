#!/usr/bin/env python3
"""분할기 엔트리 — Olist CSV → 점포(엣지노드)별 데이터 샤드.

  python scripts/prepare_edges.py                      # 636 노드(state/city)
  python scripts/prepare_edges.py --granularity seller # 셀러 3,095개
  python scripts/prepare_edges.py --events reviews     # 리뷰만

로직은 src/edge_simulator/prepare.py 에 있다.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from edge_simulator import prepare
from edge_simulator.config import data_dir, edges_dir
from edge_simulator.logging_setup import setup_logging


def main() -> None:
    ap = argparse.ArgumentParser(description="Olist → 점포별 샤드")
    ap.add_argument("--data-dir", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--granularity", choices=["state_city", "seller"], default="state_city")
    ap.add_argument("--events", choices=["all", "orders", "reviews"], default="all")
    ap.add_argument("--sim-today", default=None, help="기준일 YYYY-MM-DD (기본 env SIM_TODAY)")
    args = ap.parse_args()

    setup_logging("edge_simulator")
    dd = (args.data_dir or data_dir()).resolve()
    out = (args.out or edges_dir()).resolve()
    sim_today = pd.Timestamp(args.sim_today or os.environ.get("SIM_TODAY", "2026-05-31"), tz="UTC")

    node_rows, by_type, max_ts = prepare.build(dd, args.granularity, args.events)
    prepare.write_shards(node_rows, by_type, max_ts, out, sim_today, args.granularity, args.events)


if __name__ == "__main__":
    main()
