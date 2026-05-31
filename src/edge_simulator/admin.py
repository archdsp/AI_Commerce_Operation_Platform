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
    topics = sorted(await admin.list_topics())
    logger.info("topics: {}", topics or "(없음)")
    return topics


async def create_topics(cfg: KafkaConfig, admin) -> list[str]:
    from aiokafka.admin import NewTopic

    existing = set(await admin.list_topics())
    new = [NewTopic(t, num_partitions=p, replication_factor=cfg.replication)
           for t, p in cfg.topic_partitions.items() if t not in existing]
    if not new:
        logger.info("모든 토픽이 이미 존재")
        return []
    await admin.create_topics(new)
    names = [t.name for t in new]
    logger.success("created: {}", names)
    return names


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
