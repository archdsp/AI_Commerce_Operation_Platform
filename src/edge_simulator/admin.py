"""Kafka/MSK 토픽 관리 (aiokafka admin) — 생성 / 리셋 / 목록."""
from __future__ import annotations

import asyncio

from loguru import logger

from .config import KafkaConfig
from .kafka_auth import aiokafka_security_kwargs


async def make_admin(cfg: KafkaConfig):
    from aiokafka.admin import AIOKafkaAdminClient

    kw = dict(bootstrap_servers=cfg.bootstrap, request_timeout_ms=30000)
    kw.update(aiokafka_security_kwargs(cfg))
    admin = AIOKafkaAdminClient(**kw)
    await admin.start()
    return admin


async def list_topics(admin) -> list[str]:
    names = sorted(await admin.list_topics())
    shown = [n for n in names if not n.startswith("__")]
    try:    # 파티션 수까지 표시(검증용)
        desc = await admin.describe_topics(shown)
        counts = {d["topic"]: len(d["partitions"]) for d in desc}
        for n in shown:
            logger.info("  {:24} partitions={}", n, counts.get(n, "?"))
    except Exception as exc:  # noqa: BLE001
        logger.info("topics: {} (describe 미지원: {})", names, exc)
    return names


async def create_topics(cfg: KafkaConfig, admin) -> list[str]:
    from aiokafka.admin import NewTopic

    existing = set(await admin.list_topics())
    created: list[str] = []
    for topic, spec in cfg.topic_specs.items():
        if topic in existing:
            continue
        configs = spec.get("configs") or None
        try:
            await admin.create_topics([NewTopic(topic, num_partitions=spec["partitions"],
                                                replication_factor=cfg.replication,
                                                topic_configs=configs)])
            created.append(topic)
            logger.success("created {} (p={}, {})", topic, spec["partitions"], configs or {})
        except Exception as exc:  # noqa: BLE001  (MSK가 특정 config 거부 시 config 없이 재시도)
            logger.warning("create {} 실패({}) → config 없이 재시도", topic, exc)
            try:
                await admin.create_topics([NewTopic(topic, num_partitions=spec["partitions"],
                                                    replication_factor=cfg.replication)])
                created.append(topic)
                logger.success("created {} (p={}, no configs)", topic, spec["partitions"])
            except Exception as exc2:  # noqa: BLE001
                logger.error("create {} 재시도 실패: {}", topic, exc2)
    if not created:
        logger.info("새로 생성된 토픽 없음")
    return created


async def delete_topics(cfg: KafkaConfig, admin) -> list[str]:
    existing = set(await admin.list_topics())
    targets = [t for t in cfg.topic_partitions if t in existing]
    if not targets:
        logger.info("삭제할 토픽 없음")
        return []
    await admin.delete_topics(targets)
    logger.success("deleted: {}", targets)
    return targets


async def run_admin(cfg: KafkaConfig, action: str) -> None:
    """action ∈ {list, create, reset}."""
    admin = await make_admin(cfg)
    try:
        if action == "reset":
            logger.info("[reset] 삭제")
            await delete_topics(cfg, admin)
            await asyncio.sleep(5)
            await admin.close()                 # stale 메타데이터 회피 위해 재연결
            admin = await make_admin(cfg)
            logger.info("[reset] 재생성")
            await create_topics(cfg, admin)
        elif action == "create":
            await create_topics(cfg, admin)
        await list_topics(admin)
    finally:
        await admin.close()
