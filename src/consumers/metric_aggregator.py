"""Metric Aggregator — `review_analyzed` 소비 → 카테고리·일자 집계 → `daily_category_metrics`
UPSERT → `metric_updated` 발행.

집계는 RDS MySQL **서버사이드 1쿼리**(교차스키마 조인 commerce_ops.review_analysis ⋈ olist_raw.*)로
영향받은 날짜만 전체 재계산(idempotent). 교차리전 라운드트립 최소화.

지표(per metric_date=sim_review_date, category):
- gmv = 리뷰된 주문 라인 합계, units_sold = 라인 수, order_count = distinct 주문
- avg_review_score, negative_review_count, voc_quality_count, voc_delivery_count = distinct 리뷰 기준
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

EVENT_NS = uuid.UUID("0b3e6a52-2f7a-4c9b-9b1e-2a1d3c4f5e6a")
GROUP_ID = "metric-aggregator-v1"

_CAT = "COALESCE(ct.product_category_name_english, p.product_category_name, 'unknown')"

AGG_SQL = f"""
INSERT INTO commerce_ops.daily_category_metrics
  (metric_date, category_name_en, gmv, order_count, units_sold, avg_review_score,
   negative_review_count, voc_quality_count, voc_delivery_count, loaded_at)
SELECT ra.sim_review_date, {_CAT},
       ROUND(SUM(oi.price),2), COUNT(DISTINCT ra.order_id), COUNT(*),
       ROUND(AVG(ra.review_score),3),
       COUNT(DISTINCT CASE WHEN ra.sentiment='negative' THEN ra.review_id END),
       COUNT(DISTINCT CASE WHEN ra.voc_category='quality'  THEN ra.review_id END),
       COUNT(DISTINCT CASE WHEN ra.voc_category='delivery' THEN ra.review_id END),
       NOW()
FROM commerce_ops.review_analysis ra
JOIN olist_raw.order_items oi ON oi.order_id = ra.order_id
JOIN olist_raw.products p     ON p.product_id = oi.product_id
LEFT JOIN olist_raw.category_translation ct ON ct.product_category_name = p.product_category_name
WHERE ra.sim_review_date IN ({{placeholders}})
GROUP BY ra.sim_review_date, {_CAT}
ON DUPLICATE KEY UPDATE
  gmv=VALUES(gmv), order_count=VALUES(order_count), units_sold=VALUES(units_sold),
  avg_review_score=VALUES(avg_review_score), negative_review_count=VALUES(negative_review_count),
  voc_quality_count=VALUES(voc_quality_count), voc_delivery_count=VALUES(voc_delivery_count), loaded_at=NOW()
"""

SELECT_SQL = """
SELECT metric_date, category_name_en, gmv, negative_review_count
FROM commerce_ops.daily_category_metrics
WHERE metric_date IN ({placeholders})
"""


@dataclass
class AggregatorOptions:
    duration: float = 0.0
    batch: int = 1000


async def run(cfg: KafkaConfig, opts: AggregatorOptions) -> dict:
    from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

    sec = aiokafka_security_kwargs(cfg)
    consumer = AIOKafkaConsumer(cfg.analyzed_topic, bootstrap_servers=cfg.bootstrap,
                                group_id=GROUP_ID, auto_offset_reset="earliest",
                                enable_auto_commit=True, **sec)
    producer = AIOKafkaProducer(bootstrap_servers=cfg.bootstrap, acks="all", **sec)
    db = mysql_conn(database=OPS_DB)

    await consumer.start()
    await producer.start()
    stats: Counter = Counter()
    emitted: dict = {}          # (date,cat) → (gmv,neg) : 변경분만 metric_updated 발행
    t0 = time.monotonic()
    last = t0
    deadline = (t0 + opts.duration) if opts.duration and opts.duration > 0 else None
    logger.info("Metric Aggregator 시작 | group={} | duration={}",
                GROUP_ID, f"{opts.duration:g}s" if deadline else "∞")
    try:
        while not (deadline and time.monotonic() >= deadline):
            batch = await consumer.getmany(timeout_ms=1000, max_records=opts.batch)
            dates = set()
            for _tp, msgs in batch.items():
                for m in msgs:
                    stats["consumed"] += 1
                    try:
                        d = json.loads(m.value)["payload"].get("sim_review_date")
                        if d:
                            dates.add(d)
                    except Exception:  # noqa: BLE001
                        stats["bad"] += 1
            if not dates:
                continue

            dlist = sorted(dates)
            ph = ",".join(["%s"] * len(dlist))
            updated: list = []

            def _agg(dlist=dlist, ph=ph):
                with db.cursor() as cur:
                    cur.execute(AGG_SQL.format(placeholders=ph), dlist)
                    cur.execute(SELECT_SQL.format(placeholders=ph), dlist)
                    updated[:] = cur.fetchall()

            try:
                commit_with_retry(db, _agg)        # 데드락 시 재시도(멱등 재계산)
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                logger.error("집계 UPSERT 실패: {}", exc)
                continue
            stats["rows_upserted"] += len(updated)

            occurred = datetime.now(timezone.utc).isoformat()
            for metric_date, cat, gmv, neg in updated:
                key = (str(metric_date), cat)
                val = (float(gmv or 0), int(neg or 0))
                if emitted.get(key) == val:        # 값 변경 없으면 재발행 생략(과다발행 방지)
                    continue
                emitted[key] = val
                ev = {
                    "event_id": str(uuid.uuid5(EVENT_NS, f"metric_updated:{metric_date}:{cat}")),
                    "event_type": "metric_updated", "occurred_at": occurred,
                    "payload": {"metric_date": str(metric_date), "category_name_en": cat,
                                "gmv": val[0], "negative_review_count": val[1],
                                "aggregation_scope": "category_daily"},
                }
                await producer.send(cfg.metric_topic, json.dumps(ev, ensure_ascii=False).encode(),
                                    key=f"{metric_date}|{cat}".encode())
                stats["metric_updated"] += 1

            now = time.monotonic()
            if now - last >= 2.0:
                logger.info("consumed={} rows_upserted={} metric_updated={} | {:.0f} msg/s",
                            stats["consumed"], stats["rows_upserted"], stats["metric_updated"],
                            stats["consumed"] / (now - t0))
                last = now
    finally:
        await producer.flush()
        await consumer.stop()
        await producer.stop()
        db.close()

    dur = time.monotonic() - t0
    logger.success("종료 | consumed={} metric_updated={} | {:.1f}s",
                   stats["consumed"], stats["metric_updated"], dur)
    return dict(stats)
