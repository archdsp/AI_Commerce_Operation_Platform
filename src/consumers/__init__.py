"""Kafka 스트림 컨슈머 (모듈 패키지).

review_created → [Review Analyzer] → review_analyzed → [Metric Aggregator] → metric_updated
공유 인프라(KafkaConfig·인증·로깅)는 edge_simulator 패키지를 재사용한다.
CLI 엔트리는 scripts/ (예: scripts/review_analyzer.py).
"""
