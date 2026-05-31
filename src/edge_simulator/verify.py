"""발행 도착 검증 — 토픽을 earliest로 구독해 건수/샘플 확인."""
from __future__ import annotations

import json
import time
from collections import Counter

from loguru import logger

from .config import KafkaConfig
from .kafka_auth import aiokafka_security_kwargs


async def consume_check(cfg: KafkaConfig, sample: int = 0, budget: float = 20.0) -> dict:
    from aiokafka import AIOKafkaConsumer

    kw = dict(
        bootstrap_servers=cfg.bootstrap,
        enable_auto_commit=False,
        group_id=f"verify-{int(time.time())}",   # 매 실행 새 그룹 → earliest 재소비
        auto_offset_reset="earliest",
    )
    kw.update(aiokafka_security_kwargs(cfg))
    consumer = AIOKafkaConsumer(cfg.order_topic, cfg.review_topic, **kw)
    await consumer.start()
    counts: Counter = Counter()
    shown: Counter = Counter()
    deadline = time.monotonic() + budget
    try:
        while time.monotonic() < deadline:
            batch = await consumer.getmany(timeout_ms=2000, max_records=2000)
            if not batch:
                if counts:
                    break
                continue
            for tp, msgs in batch.items():
                for m in msgs:
                    counts[tp.topic] += 1
                    if shown[tp.topic] < sample:
                        v = json.loads(m.value)
                        logger.info("▸ {} p{}@{} key={} {} occurred={} region={}/{}",
                                    tp.topic, m.partition, m.offset, m.key.decode()[:18],
                                    v["event_type"], v["occurred_at"][:19],
                                    v["payload"].get("seller_state"), v["payload"].get("seller_city"))
                        shown[tp.topic] += 1
    finally:
        try:
            await consumer.stop()
        except BaseException:  # noqa: BLE001  (그룹 코디네이터 종료 노이즈 무시)
            pass
    logger.success("consumed {} | TOTAL {:,}", dict(counts), sum(counts.values()))
    return dict(counts)
