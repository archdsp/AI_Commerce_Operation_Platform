"""Kafka/MSK 인증 공통 — producer/admin/verify가 공유 (중복 제거).

SASL_SSL  → AWS MSK IAM (OAUTHBEARER + aws-msk-iam-sasl-signer)
SSL       → TLS
그 외      → PLAINTEXT (로컬 Kafka)
"""
from __future__ import annotations

import asyncio
import ssl
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import KafkaConfig


def _msk_token_provider(region: str):
    from aiokafka.abc import AbstractTokenProvider
    from aws_msk_iam_sasl_signer import MSKAuthTokenProvider

    class MSKTokenProvider(AbstractTokenProvider):
        async def token(self) -> str:
            loop = asyncio.get_running_loop()
            token, _ = await loop.run_in_executor(
                None, lambda: MSKAuthTokenProvider.generate_auth_token(region)
            )
            return token

    return MSKTokenProvider()


def aiokafka_security_kwargs(cfg: "KafkaConfig") -> dict:
    """aiokafka Producer/Consumer/Admin에 넘길 보안 관련 kwargs."""
    if cfg.security == "SASL_SSL":
        return dict(
            security_protocol="SASL_SSL",
            sasl_mechanism="OAUTHBEARER",
            sasl_oauth_token_provider=_msk_token_provider(cfg.region),
            ssl_context=ssl.create_default_context(),
        )
    if cfg.security == "SSL":
        return dict(security_protocol="SSL", ssl_context=ssl.create_default_context())
    return dict(security_protocol="PLAINTEXT")
