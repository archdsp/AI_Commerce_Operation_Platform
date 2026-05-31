"""Review Analyzer — `review_created` 소비 → 감성/VOC 분석 → `review_analysis` UPSERT(멱등)
→ `review_analyzed` 발행. 분석/파싱 실패는 `review_created.dlq`로 격리.

- DB: RDS MySQL (commerce_ops.review_analysis), review_id 기준 멱등 UPSERT
- 교차리전 최적화: 배치 multi-row INSERT … ON DUPLICATE KEY UPDATE (pymysql executemany)
- --duration: N초 후 자동 종료(비용 제어)
공유 인프라(KafkaConfig·인증·DB)는 edge_simulator / common 재사용.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone

from loguru import logger

from common.db import OPS_DB, commit_with_retry, mysql_conn
from edge_simulator.config import KafkaConfig
from edge_simulator.kafka_auth import aiokafka_security_kwargs

from .analysis import analyze

EVENT_NS = uuid.UUID("0b3e6a52-2f7a-4c9b-9b1e-2a1d3c4f5e6a")
GROUP_ID = "review-analyzer-v1"

# MySQL UPSERT — 전부 플레이스홀더 튜플이라 pymysql이 multi-row로 배치 최적화(교차리전 RTT 절감)
UPSERT_SQL = """
INSERT INTO review_analysis
  (review_id, order_id, product_id, review_score, sentiment, voc_category, confidence, analyzed_at, sim_review_date)
VALUES
  (%(review_id)s,%(order_id)s,%(product_id)s,%(review_score)s,%(sentiment)s,%(voc_category)s,%(confidence)s,%(analyzed_at)s,%(sim_review_date)s)
ON DUPLICATE KEY UPDATE
  sentiment=VALUES(sentiment), voc_category=VALUES(voc_category), confidence=VALUES(confidence),
  review_score=VALUES(review_score), analyzed_at=VALUES(analyzed_at), sim_review_date=VALUES(sim_review_date)
"""


@dataclass
class ConsumerOptions:
    analyzer: str = "heuristic"   # heuristic | llm(RunPod)
    duration: float = 0.0         # N초 후 종료 (0=무제한)
    batch: int = 500
    use_db: bool = True


async def run(cfg: KafkaConfig, opts: ConsumerOptions) -> dict:
    from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

    sec = aiokafka_security_kwargs(cfg)
    consumer = AIOKafkaConsumer(cfg.review_topic, bootstrap_servers=cfg.bootstrap,
                                group_id=GROUP_ID, auto_offset_reset="earliest",
                                enable_auto_commit=True, **sec)
    producer = AIOKafkaProducer(bootstrap_servers=cfg.bootstrap, acks="all", **sec)
    dlq_topic = f"{cfg.review_topic}.dlq"

    db = mysql_conn(database=OPS_DB) if opts.use_db else None

    await consumer.start()
    await producer.start()
    stats: Counter = Counter()
    t0 = time.monotonic()
    last = t0
    deadline = (t0 + opts.duration) if opts.duration and opts.duration > 0 else None
    logger.info("Review Analyzer 시작 | analyzer={} | db={} | group={} | duration={}",
                opts.analyzer, "MySQL" if db else "off", GROUP_ID, f"{opts.duration:g}s" if deadline else "∞")
    try:
        while not (deadline and time.monotonic() >= deadline):
            batch = await consumer.getmany(timeout_ms=1000, max_records=opts.batch)
            now_dt = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)
            rows, analyzed = [], []
            for _tp, msgs in batch.items():
                for m in msgs:
                    stats["consumed"] += 1
                    try:
                        env = json.loads(m.value)
                        p = env["payload"]
                        a = analyze(p.get("review_score"), p.get("review_comment_title"),
                                    p.get("review_comment_message"), opts.analyzer)
                        rows.append(dict(review_id=p["review_id"], order_id=p.get("order_id"),
                                         product_id=p.get("product_id"), review_score=p.get("review_score"),
                                         sentiment=a.sentiment, voc_category=a.voc_category,
                                         confidence=a.confidence, analyzed_at=now_dt,
                                         sim_review_date=p.get("sim_review_date")))
                        analyzed.append((p["review_id"], {
                            "event_id": str(uuid.uuid5(EVENT_NS, f"review_analyzed:{p['review_id']}")),
                            "event_type": "review_analyzed", "occurred_at": env.get("occurred_at"),
                            "payload": {"review_id": p["review_id"], "order_id": p.get("order_id"),
                                        "product_id": p.get("product_id"), "sentiment": a.sentiment,
                                        "voc_category": a.voc_category, "confidence": a.confidence,
                                        "sim_review_date": p.get("sim_review_date")},
                        }))
                    except Exception as exc:  # noqa: BLE001  (poison → DLQ)
                        stats["dlq"] += 1
                        await producer.send(dlq_topic, m.value, key=m.key)
                        logger.warning("분석 실패 → DLQ: {}", exc)

            if rows and db is not None:
                def _upsert(rows=rows):
                    with db.cursor() as cur:
                        cur.executemany(UPSERT_SQL, rows)
                try:
                    commit_with_retry(db, _upsert)      # 데드락 시 재시도(멱등 UPSERT)
                    stats["written"] += len(rows)
                except Exception as exc:  # noqa: BLE001
                    db.rollback()
                    logger.error("MySQL UPSERT 실패: {}", exc)

            for rid, ev in analyzed:
                await producer.send(cfg.analyzed_topic, json.dumps(ev, ensure_ascii=False).encode(), key=rid.encode())
                stats["analyzed"] += 1

            now = time.monotonic()
            if now - last >= 2.0 and stats["consumed"]:
                logger.info("consumed={} written={} analyzed={} dlq={} | {:.0f} msg/s",
                            stats["consumed"], stats["written"], stats["analyzed"], stats["dlq"],
                            stats["consumed"] / (now - t0))
                last = now
    finally:
        await producer.flush()
        await consumer.stop()
        await producer.stop()
        if db is not None:
            db.close()

    dur = time.monotonic() - t0
    logger.success("종료 | consumed={} written={} analyzed={} dlq={} | {:.1f}s",
                   stats["consumed"], stats["written"], stats["analyzed"], stats["dlq"], dur)
    return dict(stats)
