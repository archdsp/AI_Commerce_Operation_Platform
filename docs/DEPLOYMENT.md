> **상태:** 구현 반영(REALIGNED) — 실제 스택: RDS MySQL · MSK(IAM) · MWAA · RunPod vLLM(Qwen2.5-7B) · Qdrant · AWS API Gateway. 본 문서의 PostgreSQL/Redis/Docker Compose/OpenAI·Claude 언급은 구현과 다름 — 스택 매핑·완성도는 [PROGRESS.md](../PROGRESS.md) 참조.

# 배포 가이드 (사전 설계)

| 항목 | 내용 |
|------|------|
| 문서 버전 | 1.0 |
| 작성일 | 2026-05-31 |
| 대상 환경 | Docker Compose (로컬/EC2) |

---

## 1. 사전 요구사항

| 항목 | 최소 버전 |
|------|-----------|
| Docker | 24+ |
| Docker Compose | v2.20+ |
| 디스크 | 20 GB 여유 |
| RAM | 8 GB (Airflow+Kafka+Postgres) |
| OS | Ubuntu 22.04 LTS (EC2 권장) |

외부:

- OpenAI API Key 및/또는 Anthropic API Key
- Olist CSV (Kaggle 다운로드, [DATA.md](./DATA.md))

---

## 2. Docker Compose 서비스 (예정)

| 서비스 | 이미지/빌드 | 포트 | 역할 |
|--------|-------------|------|------|
| `postgres` | postgres:16 | 5432 | olist_raw + commerce_ops DB |
| `redis` | redis:7-alpine | 6379 | 캐시·Rate Limit·세션 |
| `zookeeper` | confluentinc/cp-zookeeper | 2181 | Kafka 의존 |
| `kafka` | confluentinc/cp-kafka | 9092 | 이벤트 |
| `gateway` | build `./gateway` | 8000 | FastAPI AI Gateway |
| `agent-worker` | build `./agents` | — | LangGraph Runtime |
| `review-analyzer` | build `./workers` | — | Kafka consumer |
| `metric-aggregator` | build `./workers` | — | Kafka consumer |
| `usage-logger` | build `./workers` | — | Kafka consumer |
| `airflow-webserver` | apache/airflow:2.8 | 8080 | UI |
| `airflow-scheduler` | apache/airflow:2.8 | — | DAG 실행 |
| `airflow-init` | apache/airflow:2.8 | — | DB migrate 1회 |
| `seed` (profile) | build `./db` | — | Olist bulk load |

> **TODO (구현):** `docker-compose.yml` 실제 서비스명·healthcheck 반영 후 본 표 동기화.

---

## 3. 환경 변수 (`.env.example` 내용)

프로젝트 루트 `.env.example`에 포함할 항목 (구현 시 복사 → `.env`).

```bash
# === Application ===
APP_ENV=development
LOG_LEVEL=INFO
SIM_TODAY=2026-05-31
SIM_TZ=America/Sao_Paulo

# === Gateway ===
GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=8000
JWT_SECRET=change-me-in-production
JWT_ALGORITHM=HS256
CACHE_TTL_SECONDS=3600
RATE_LIMIT_PER_MINUTE=100

# === Database ===
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=commerce
POSTGRES_PASSWORD=change-me
POSTGRES_DB_OLIST=olist_raw
POSTGRES_DB_OPS=commerce_ops
DATABASE_URL_OLIST=postgresql://commerce:change-me@postgres:5432/olist_raw
DATABASE_URL_OPS=postgresql://commerce:change-me@postgres:5432/commerce_ops

# === Redis ===
REDIS_URL=redis://redis:6379/0

# === Kafka ===
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_REVIEW_CREATED_TOPIC=review_created
KAFKA_REVIEW_ANALYZED_TOPIC=review_analyzed
KAFKA_METRIC_UPDATED_TOPIC=metric_updated

# === LLM ===
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
DEFAULT_CHAT_MODEL=gpt-4o-mini
DEFAULT_INSIGHT_MODEL=claude-3-5-sonnet-20241022
ENABLED_MODELS=gpt-4o-mini,claude-3-5-sonnet-20241022

# === Airflow ===
AIRFLOW__CORE__EXECUTOR=LocalExecutor
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://commerce:change-me@postgres:5432/airflow
AIRFLOW__CORE__LOAD_EXAMPLES=False
AIRFLOW_UID=50000

# === Olist Seed ===
OLIST_DATA_DIR=./data/olist
```

> **TODO (구현):** `.env.example` 파일 생성 및 `docker compose config` 검증.

---

## 4. 시작 순서

```mermaid
flowchart TD
    A[1. .env 작성] --> B[2. docker compose up -d postgres redis]
    B --> C[3. DB 생성 + schema apply]
    C --> D[4. olist seed]
    D --> E[5. zookeeper + kafka]
    E --> F[6. workers]
    F --> G[7. gateway + agent-worker]
    G --> H[8. airflow-init]
    H --> I[9. airflow webserver + scheduler]
    I --> J[10. DAG trigger 또는 wait schedule]
```

### 4.1 명령 (초안)

```bash
cp .env.example .env
# API 키·비밀번호 편집

docker compose up -d postgres redis
docker compose run --rm db-migrate    # TODO: 구현
docker compose --profile seed run --rm seed

docker compose up -d zookeeper kafka
docker compose up -d review-analyzer metric-aggregator usage-logger

docker compose up -d gateway agent-worker

docker compose up airflow-init
docker compose up -d airflow-webserver airflow-scheduler
```

헬스 확인:

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/ready   # DB+Redis+Kafka 연결
```

---

## 5. Olist Seed 단계

| 단계 | 작업 | 검증 |
|------|------|------|
| 1 | CSV를 `data/olist/`에 배치 | 파일 8개 존재 |
| 2 | `seed` 서비스 실행 | `olist_raw.orders` count > 0 |
| 3 | `sim_*` 뷰/컬럼 생성 | `SIM_TODAY` 기준 샘플 SELECT |
| 4 | `commerce_ops` bootstrap | `prompt_versions`, `api_keys` 1건+ |
| 5 | (선택) Airflow backfill | `daily_category_metrics` not empty |

상세: [DATA.md §Seed](./DATA.md)

---

## 6. AWS EC2 배포 계획

| 항목 | 권장 |
|------|------|
| 인스턴스 | `t3.xlarge` (4 vCPU, 16 GB) — PoC |
| OS | Ubuntu 22.04 |
| 디스크 | 50 GB gp3 |
| 보안 그룹 | 22 (SSH), 8000 (Gateway), 8080 (Airflow, 내부만), 5432/9092 **비공개** |
| TLS | v1: 생략 또는 Nginx + Let's Encrypt **TODO** |

### 6.1 배포 절차 (개요)

1. EC2 생성 · Docker 설치
2. `git clone` + `.env` (Secrets Manager 연동 **TODO**)
3. `docker compose up -d` (§4 순서)
4. k6를 별도 머신 또는 동일 EC2에서 실행 ([LOAD_TEST.md](./LOAD_TEST.md))

### 6.2 운영

| 항목 | v1 |
|------|-----|
| 로그 | `docker compose logs -f gateway` |
| 백업 | Postgres volume 스냅샷 **TODO** |
| 모니터링 | CloudWatch agent **TODO** |

---

## 7. 트러블슈팅

> **TODO (구현·운영 검증 후):** 실제 장애 사례별 원인·해결책을 채운다.

| 증상 | 확인 | 조치 (플레이스홀더) |
|------|------|---------------------|
| Gateway 503 ready | `docker compose ps`, Postgres/Kafka | 의존 서비스 기동 순서 재확인 |
| Agent timeout | LLM API 키, 네트워크 | `OPENAI_API_KEY` 설정 |
| Kafka lag 증가 | consumer group | worker 스케일 **TODO** |
| Airflow task fail | UI Log | `quality_check` 규칙·데이터 **TODO** |
| Cache hit 0% | Redis 연결 | `REDIS_URL` |
| SQL_REJECTED | AGENTS.md 가드레일 | 질의/프롬프트 조정 |

---

## 8. 관련 문서

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [DATA.md](./DATA.md)
- [LOAD_TEST.md](./LOAD_TEST.md)

---

## 9. 변경 이력

| 버전 | 날짜 | 변경 |
|------|------|------|
| 1.0 | 2026-05-31 | 배포 사전 설계 초안 |
