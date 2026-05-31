"""샤드 → Kafka/MSK 발행 (시뮬레이터 코어).

각 점포(노드)를 async 태스크로 돌리며, 원본 타임라인을 TAF 가속(또는 고정 rate)으로 재생.
key=seller_id. --scale로 합성복제, --shard-index/count로 다중 프로듀서 분산.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from .config import KafkaConfig
from .kafka_auth import aiokafka_security_kwargs
from .shards import load_records


@dataclass
class RunOptions:
    taf: float = 8760.0
    rate: float = 0.0
    scale: int = 1
    shard_index: int = 0
    shard_count: int = 1
    max_events: int = 0
    max_sleep: float = 1.0
    loop: bool = False
    dry_run: bool = False
    events: str = "all"


class Pacer:
    """전역 고정 레이트(초당 rate건). --rate 지정 시."""

    def __init__(self, rate: float):
        self.interval = 1.0 / rate if rate > 0 else 0.0
        self.lock = asyncio.Lock()
        self.next_t = time.monotonic()

    async def wait(self) -> None:
        if self.interval <= 0:
            return
        async with self.lock:
            now = time.monotonic()
            if now < self.next_t:
                await asyncio.sleep(self.next_t - now)
            self.next_t = max(self.next_t, now) + self.interval


def expand(rec: dict, scale: int):
    """--scale K: 레코드를 K개 합성 점포 변형으로 (id 네임스페이스 분리, event_id 재도출)."""
    if scale <= 1:
        yield rec["key"], rec["kind"], rec["value"]
        return
    base = rec["value"]
    for k in range(scale):
        if k == 0:
            yield rec["key"], rec["kind"], base
            continue
        v = json.loads(json.dumps(base))
        v["event_id"] = f"{base['event_id']}:r{k}"
        p = v["payload"]
        for idf in ("seller_id", "order_id", "review_id"):
            if p.get(idf):
                p[idf] = f"syn{k}:{p[idf]}"
        yield f"{rec['key']}-r{k}", rec["kind"], v


async def make_producer(cfg: KafkaConfig):
    from aiokafka import AIOKafkaProducer

    kw = dict(
        bootstrap_servers=cfg.bootstrap,
        acks="all",
        linger_ms=20,
        compression_type="gzip",
        client_id="store-simulator",
        max_batch_size=256 * 1024,
    )
    kw.update(aiokafka_security_kwargs(cfg))
    p = AIOKafkaProducer(**kw)
    await p.start()
    return p


async def run(cfg: KafkaConfig, edges_dir: Path, opts: RunOptions) -> dict:
    nodes = load_records(edges_dir, opts.shard_index, opts.shard_count, opts.events)
    pacer = Pacer(opts.rate) if opts.rate else None
    taf = max(opts.taf, 0.001)
    counters = {"n": 0, "err": 0}
    t0 = time.monotonic()
    stop = asyncio.Event()
    producer = None if opts.dry_run else await make_producer(cfg)

    async def emit(topic: str, key: str, value: dict) -> None:
        if producer is None:
            counters["n"] += 1
            return
        try:
            await producer.send(topic, json.dumps(value, ensure_ascii=False).encode(), key=key.encode())
            counters["n"] += 1
        except Exception as exc:  # noqa: BLE001
            counters["err"] += 1
            logger.error("send 실패: {}", exc)

    async def run_node(records: list[dict]) -> None:
        prev = records[0]["_ts"]
        for rec in records:
            if stop.is_set():
                return
            if pacer:
                await pacer.wait()
            else:
                gap = (rec["_ts"] - prev).total_seconds() / taf
                if gap > 0:
                    await asyncio.sleep(min(gap, opts.max_sleep))
            prev = rec["_ts"]
            for key, kind, value in expand(rec, opts.scale):
                await emit(cfg.topic_for_kind(kind), key, value)
                if opts.max_events and counters["n"] >= opts.max_events:
                    stop.set()
                    return

    async def reporter() -> None:
        while not stop.is_set():
            await asyncio.sleep(1.0)
            el = time.monotonic() - t0
            logger.info("sent={:,} | {:,.0f} msg/s | err={}", counters["n"],
                        counters["n"] / el if el else 0, counters["err"])

    logger.info("{} | {} | scale=×{} | 점포≈{:,}",
                "DRY-RUN" if opts.dry_run else f"PRODUCE→{cfg.bootstrap}",
                f"rate={opts.rate:g}/s" if opts.rate else f"taf={taf:g}",
                opts.scale, len(nodes) * opts.scale)
    rep = asyncio.create_task(reporter())
    try:
        while True:
            await asyncio.gather(*(run_node(recs) for _, recs in nodes))
            if not opts.loop or stop.is_set():
                break
            logger.info("[loop] 처음부터 재생")
    finally:
        stop.set()
        rep.cancel()
        if producer is not None:
            await producer.flush()
            await producer.stop()

    dur = time.monotonic() - t0
    logger.success("done sent={:,} err={} | {:.1f}s | {:,.0f} msg/s avg",
                   counters["n"], counters["err"], dur, counters["n"] / dur if dur else 0)
    return counters
