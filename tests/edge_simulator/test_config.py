"""config 모듈 — KafkaConfig 환경 파싱."""
from edge_simulator.config import KafkaConfig


def test_kafka_config_plaintext(monkeypatch):
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    monkeypatch.setenv("KAFKA_SECURITY_PROTOCOL", "plaintext")
    monkeypatch.setenv("KAFKA_ORDER_EVENTS_TOPIC", "order_events")
    monkeypatch.setenv("KAFKA_REVIEW_CREATED_TOPIC", "review_created")
    monkeypatch.delenv("KAFKA_REPLICATION", raising=False)

    cfg = KafkaConfig.from_env()
    assert cfg.security == "PLAINTEXT"           # 대문자 정규화
    assert cfg.replication == 1                  # PLAINTEXT → RF 1
    assert cfg.topic_for_kind("order") == "order_events"
    assert cfg.topic_for_kind("review") == "review_created"
    assert {"order_events", "review_created"} <= set(cfg.topic_partitions)
    assert cfg.topic_partitions["order_events"] == 12       # 권장 파티션 반영
    assert cfg.topic_partitions["review_created"] == 6
    # metric_updated는 log compaction, DLQ 토픽 포함
    assert cfg.topic_specs["metric_updated"]["configs"].get("cleanup.policy") == "compact"
    assert "review_created.dlq" in cfg.topic_partitions
    assert "order_events.dlq" in cfg.topic_partitions


def test_kafka_config_msk(monkeypatch):
    monkeypatch.setenv("KAFKA_SECURITY_PROTOCOL", "SASL_SSL")
    monkeypatch.setenv("AWS_REGION", "ap-northeast-2")
    monkeypatch.delenv("KAFKA_REPLICATION", raising=False)

    cfg = KafkaConfig.from_env()
    assert cfg.security == "SASL_SSL"
    assert cfg.replication == 3                  # MSK → RF 3
    assert cfg.region == "ap-northeast-2"
