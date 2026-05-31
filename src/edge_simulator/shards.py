"""점포별 샤드 로딩 — produce_shards가 자기 몫(shard_index/count)만 읽는다."""
from __future__ import annotations

import glob
import json
from datetime import datetime
from pathlib import Path

from loguru import logger


def load_records(edges_dir: Path, shard_index: int = 0, shard_count: int = 1, events: str = "all"):
    """(node_name, records) 리스트 반환. records는 _ts(datetime) 포함, ts 오름차순."""
    edges_dir = Path(edges_dir)
    files = sorted(glob.glob(str(edges_dir / "*.jsonl")))
    if not files:
        raise FileNotFoundError(f"샤드 없음: {edges_dir} — 먼저 scripts/prepare_edges.py 실행")
    mine = [f for i, f in enumerate(files) if i % shard_count == shard_index]
    nodes: list[tuple[str, list[dict]]] = []
    total = 0
    for f in mine:
        recs = []
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                if events == "orders" and r["kind"] != "order":
                    continue
                if events == "reviews" and r["kind"] != "review":
                    continue
                r["_ts"] = datetime.fromisoformat(r["ts"])
                recs.append(r)
        if recs:
            recs.sort(key=lambda x: x["_ts"])
            nodes.append((Path(f).stem, recs))
            total += len(recs)
    logger.info("샤드 {}/{} (shard {}/{}) | 노드 {} | 이벤트 {:,}",
                len(mine), len(files), shard_index, shard_count, len(nodes), total)
    return nodes
