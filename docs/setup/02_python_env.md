# 02. Python 환경

## 구성요소
가상환경 + 의존성 + `.env`. 모든 스크립트/모듈의 실행 기반.

## 1) 가상환경 (택1)
```bash
# venv
python3 -m venv .venv && source .venv/bin/activate
# 또는 conda
conda create -n cj-edge-store python=3.11 -y && conda activate cj-edge-store
```

## 2) 의존성
```bash
pip install -r requirements.txt
```
주요 패키지: `pandas` `aiokafka` `aws-msk-iam-sasl-signer` `confluent-kafka` `python-dotenv` `loguru` `psycopg2-binary` `pytest` `pytest-asyncio`

## 3) .env 구성
```bash
cp .env.example .env
```
시뮬레이터/MSK 관련 키:
```bash
OLIST_DATA_DIR=/home/ubuntu/Workspace/data
KAFKA_BOOTSTRAP_SERVERS=boot-xxxx.kafka-serverless.ap-northeast-2.amazonaws.com:9098
KAFKA_SECURITY_PROTOCOL=SASL_SSL        # 로컬 Kafka면 PLAINTEXT
AWS_REGION=ap-northeast-2
KAFKA_ORDER_EVENTS_TOPIC=order_events
KAFKA_REVIEW_CREATED_TOPIC=review_created
SIM_TODAY=2026-05-31
TAF=8760
SYNTH_REPLICATION=1
# (선택) 로그 베이스 경로 — 기본 /workspace/app_logs
# APP_LOG_DIR=/workspace/app_logs
```

## 4) 로깅 (loguru)
- 모든 엔트리는 시작 시 `setup_logging("edge_simulator")` 호출
- 로그: `${APP_LOG_DIR:-/workspace/app_logs}/edge_simulator/edge_simulator_{date}.log` (50MB 회전, 7일 보관) + 콘솔
```bash
sudo mkdir -p /workspace/app_logs && sudo chown -R $USER /workspace   # 최초 1회
```

## 5) 테스트
```bash
pytest tests/edge_simulator -v
```

> 다음: [03_database.md](./03_database.md)
