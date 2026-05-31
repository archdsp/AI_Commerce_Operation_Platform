"""Qdrant Loader — `review_created` 소비 → 리뷰 텍스트 임베딩(384-d) → Qdrant `reviews` upsert.

RAG 적재 단계: edge→MSK→(분석=RDS) 와 병행해, 같은 리뷰를 벡터로 적재해 의미 검색 기반을 만든다.
- point id = uuid5(review_id) → 멱등 upsert
- payload = {review_id, order_id, score, text} (기존 컬렉션 스키마와 일치)
- --duration 비용 제어
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from collections import Counter
from dataclasses import dataclass

from loguru import logger

from common.embeddings import EMBED_DIM, embed
from edge_simulator.config import KafkaConfig
from edge_simulator.kafka_auth import aiokafka_security_kwargs

NS = uuid.UUID("0b3e6a52-2f7a-4c9b-9b1e-2a1d3c4f5e6a")
GROUP_ID = "qdrant-loader-v1"
COLLECTION = os.environ.get("QDRANT_COLLECTION", "reviews")


@dataclass
class LoaderOptions:
    duration: float = 0.0
    batch: int = 256


def _qdrant():
    from qdrant_client import QdrantClient
    return QdrantClient(url=os.environ.get("QDRANT_URL", "http://localhost:6333"),
                        api_key=os.environ.get("QDRANT_API_KEY") or None, timeout=30)


async def run(cfg: KafkaConfig, opts: LoaderOptions) -> dict:
    from aiokafka import AIOKafkaConsumer
    from qdrant_client.models import Distance, PointStruct, VectorParams

    qc = _qdrant()
    if not qc.collection_exists(COLLECTION):
        qc.create_collection(COLLECTION, vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE))
        logger.info("Qdrant 컬렉션 생성: {} (dim={})", COLLECTION, EMBED_DIM)

    sec = aiokafka_security_kwargs(cfg)
    consumer = AIOKafkaConsumer(cfg.review_topic, bootstrap_servers=cfg.bootstrap, group_id=GROUP_ID,
                                auto_offset_reset="earliest", enable_auto_commit=True, **sec)
    await consumer.start()
    stats: Counter = Counter()
    t0 = time.monotonic()
    last = t0
    deadline = (t0 + opts.duration) if opts.duration and opts.duration > 0 else None
    logger.info("Qdrant Loader 시작 | collection={} dim={} | duration={}",
                COLLECTION, EMBED_DIM, f"{opts.duration:g}s" if deadline else "∞")
    try:
        while not (deadline and time.monotonic() >= deadline):
            batch = await consumer.getmany(timeout_ms=1000, max_records=opts.batch)
            recs = []
            for _tp, msgs in batch.items():
                for m in msgs:
                    stats["consumed"] += 1
                    try:
                        p = json.loads(m.value)["payload"]
                        text = " ".join(x for x in (p.get("review_comment_title"),
                                                    p.get("review_comment_message")) if x).strip()
                        if not text:
                            text = f"(평점 {p.get('review_score')})"
                        recs.append((p["review_id"], p.get("order_id"), p.get("review_score"), text))
                    except Exception as exc:  # noqa: BLE001
                        stats["bad"] += 1
                        logger.warning("parse 실패: {}", exc)
            if recs:
                vectors = embed([r[3] for r in recs])
                points = [PointStruct(id=str(uuid.uuid5(NS, rid)), vector=vec,
                                      payload={"review_id": rid, "order_id": oid, "score": sc, "text": txt})
                          for (rid, oid, sc, txt), vec in zip(recs, vectors)]
                qc.upsert(COLLECTION, points=points)
                stats["upserted"] += len(points)
            now = time.monotonic()
            if now - last >= 2.0 and stats["consumed"]:
                logger.info("consumed={} upserted={} | {:.0f} msg/s",
                            stats["consumed"], stats["upserted"], stats["consumed"] / (now - t0))
                last = now
    finally:
        await consumer.stop()
    dur = time.monotonic() - t0
    logger.success("종료 | consumed={} upserted={} bad={} | {:.1f}s",
                   stats["consumed"], stats["upserted"], stats["bad"], dur)
    return dict(stats)
