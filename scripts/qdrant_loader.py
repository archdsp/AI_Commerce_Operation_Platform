#!/usr/bin/env python3
"""Qdrant Loader 엔트리 — review_created → 임베딩(384) → Qdrant 'reviews'(RAG 적재).

  python scripts/qdrant_loader.py --duration 60

로직은 src/consumers/qdrant_loader.py. 로그: /workspace/app_logs/qdrant_loader/.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from consumers.qdrant_loader import LoaderOptions, run
from edge_simulator.config import KafkaConfig
from edge_simulator.logging_setup import setup_logging


def main() -> None:
    ap = argparse.ArgumentParser(description="Qdrant Loader (review_created → Qdrant reviews)")
    ap.add_argument("--duration", type=float, default=0.0, help="N초 후 자동 종료(0=무제한)")
    ap.add_argument("--batch", type=int, default=256)
    args = ap.parse_args()

    setup_logging("qdrant_loader")
    asyncio.run(run(KafkaConfig.from_env(), LoaderOptions(duration=args.duration, batch=args.batch)))


if __name__ == "__main__":
    main()
