"""환경설정 (.env 로딩 + Kafka/MSK 설정 + 경로)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_LOADED = False


def load_env() -> None:
    global _ENV_LOADED
    if not _ENV_LOADED:
        load_dotenv(REPO_ROOT / ".env")
        _ENV_LOADED = True


def data_dir() -> Path:
    """Olist 원본 CSV 디렉터리 (env OLIST_DATA_DIR, 기본 ../data)."""
    load_env()
    return Path(os.environ.get("OLIST_DATA_DIR", REPO_ROOT / ".." / "data")).resolve()


def edges_dir() -> Path:
    """점포별 샤드 출력 디렉터리."""
    load_env()
    return Path(os.environ.get("EDGES_DIR", REPO_ROOT / "data" / "edges")).resolve()


@dataclass
class KafkaConfig:
    bootstrap: str
    security: str            # PLAINTEXT / SSL / SASL_SSL(MSK IAM)
    region: str
    order_topic: str
    review_topic: str
    analyzed_topic: str
    metric_topic: str

    @classmethod
    def from_env(cls) -> "KafkaConfig":
        load_env()
        region = os.environ.get("AWS_REGION", "ap-northeast-2")
        os.environ.setdefault("AWS_REGION", region)
        os.environ.setdefault("AWS_DEFAULT_REGION", region)
        return cls(
            bootstrap=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            security=os.environ.get("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT").upper(),
            region=region,
            order_topic=os.environ.get("KAFKA_ORDER_EVENTS_TOPIC", "order_events"),
            review_topic=os.environ.get("KAFKA_REVIEW_CREATED_TOPIC", "review_created"),
            analyzed_topic=os.environ.get("KAFKA_REVIEW_ANALYZED_TOPIC", "review_analyzed"),
            metric_topic=os.environ.get("KAFKA_METRIC_UPDATED_TOPIC", "metric_updated"),
        )

    @property
    def topic_partitions(self) -> dict[str, int]:
        # KAFKA.md §1: review 계열 3p / order_events 확장 6p
        return {self.review_topic: 3, self.order_topic: 6, self.analyzed_topic: 3, self.metric_topic: 3}

    @property
    def replication(self) -> int:
        # MSK(Serverless)는 RF=3 필수, 로컬 단일 브로커는 1
        return int(os.environ.get("KAFKA_REPLICATION", "1" if self.security == "PLAINTEXT" else "3"))

    def topic_for_kind(self, kind: str) -> str:
        return self.order_topic if kind == "order" else self.review_topic
