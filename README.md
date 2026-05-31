# AI Commerce Operations Platform

> Olist 커머스 데이터 기반 LLM Agent 운영 자동화 플랫폼

| 항목 | 내용 |
|------|------|
| **현재 단계** | **Pre-implementation** — 설계·문서 완료 후 코드 구현 예정 |
| 문서 | [docs/README.md](./docs/README.md) |

---

## 소개

MD·CS·운영팀의 반복 데이터 업무(매출 분석, VOC, KPI 리포트)를 **자연어 → AI Agent → PostgreSQL → 인사이트** 흐름으로 자동화합니다.

단순 챗봇이 아니라 다음을 포함하는 운영 가능한 AI 플랫폼을 목표로 합니다.

- **AI API Gateway** — 인증(API Key/JWT), Rate Limit(100/min), Redis 캐시, 사용량 추적
- **Multi Agent** — MD / VOC / Insight + Text-to-SQL
- **Kafka** — 리뷰 생성·분석·집계 이벤트
- **Airflow** — 일별 KPI·`daily_category_metrics` 사전 집계
- **PostgreSQL** — Olist 원본(`olist_raw`) + 운영 DB(`commerce_ops`)

데이터셋: [Olist Brazilian E-Commerce](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (데모·PoC)

---

## 빠른 개요

```text
Client → Gateway → Agent Router → MD | VOC | Insight → PostgreSQL
                              ↘ Kafka → Workers → review_analysis
Airflow (daily) → daily_category_metrics → Agent 조회 가속
```

| API (주요) | 설명 |
|------------|------|
| `POST /v1/chat` | 자동 Agent 라우팅 질의 |
| `POST /v1/agent/run` | 지정 Agent 실행 |
| `POST /v1/sql/generate` | Text-to-SQL |
| `GET /v1/usage` | 토큰·비용·캐시 통계 |
| `GET /v1/models` | 허용 LLM 목록 |

성능 목표: 동시 500~1,000 사용자, Cache P95 &lt; 300ms, Agent P95 &lt; 10s, 오류율 &lt; 1%, 캐시 hit &gt; 30%.

---

## 문서 (docs/)

전체 인덱스: **[docs/README.md](./docs/README.md)**

| 문서 | 내용 |
|------|------|
| [PRD](./docs/PRD.md) | 제품 요구사항 |
| [PROJECT](./docs/PROJECT.md) | 프로젝트 상세 |
| [ARCHITECTURE](./docs/ARCHITECTURE.md) | 시스템 아키텍처 |
| [ERD](./docs/ERD.md) | 데이터 모델 |
| [DATA](./docs/DATA.md) | Olist·시뮬레이션·Seed |
| [API](./docs/API.md) | REST API 명세 |
| [AGENTS](./docs/AGENTS.md) | Agent·프롬프트·가드레일 |
| [KAFKA](./docs/KAFKA.md) | 이벤트 파이프라인 |
| [AIRFLOW](./docs/AIRFLOW.md) | 배치 DAG |
| [DEPLOYMENT](./docs/DEPLOYMENT.md) | Docker·EC2 배포 |
| [LOAD_TEST](./docs/LOAD_TEST.md) | k6 부하 테스트 |
| [DEMO_SCRIPT](./docs/DEMO_SCRIPT.md) | 데모 시나리오 |

---

## 기술 스택

FastAPI · PostgreSQL · Redis · Kafka · Airflow · LangGraph · OpenAI/Claude · Docker Compose · AWS EC2 · k6

---

## 5일 개발 일정 (예정)

| 일차 | 목표 |
|------|------|
| Day 1 | DB·ERD·Seed |
| Day 2 | AI Gateway |
| Day 3 | Agents·Text-to-SQL |
| Day 4 | Kafka·Workers |
| Day 5 | Airflow·Compose·k6·데모 |

---

## 로컬 실행

> **아직 구현 전입니다.** `docker-compose.yml` 및 애플리케이션 코드 추가 후 [DEPLOYMENT.md](./docs/DEPLOYMENT.md)를 따릅니다.

```bash
# 구현 후 예시
cp .env.example .env
docker compose up -d
```

---

## 🏪 실시간 점포 시뮬레이터 (Olist → AWS MSK)

**636개 지역 점포**(엣지노드 = `seller_state`+`seller_city`)가 각자 자기 데이터를 들고 **MSK로 실시간처럼 발행**합니다. 데이터를 점포별 샤드로 미리 쪼개두고(각 점포가 자기 데이터 보유 → 현실적 엣지 토폴로지 + 빠른 시작), 프로듀서가 원본 타임라인을 시간가속(TAF)으로 재생합니다. `key=seller_id`로 점포별 순서를 보장합니다.

| 스크립트 | 역할 |
|---|---|
| `scripts/prepare_edges.py` | Olist CSV → 점포별 샤드 `data/edges/*.jsonl` + `manifest.json` |
| `scripts/run.py` | 샤드 → MSK 발행 (시뮬레이터 **엔트리**) |
| `src/edge_simulator/` | 로직 모듈 (config·prepare·shards·producer·admin·verify·logging) |
| `scripts/kafka_admin.py` | 토픽 생성 / **리셋** / 목록 |
| `scripts/consume_check.py` | 도착 검증(소비) |

### 사전 준비
`.env` (예시):
```bash
KAFKA_BOOTSTRAP_SERVERS=boot-xxxx.kafka-serverless.ap-northeast-2.amazonaws.com:9098
KAFKA_SECURITY_PROTOCOL=SASL_SSL          # MSK IAM. 로컬 Kafka면 PLAINTEXT
AWS_REGION=ap-northeast-2
OLIST_DATA_DIR=/abs/path/to/olist/csv     # CSV 9종 위치
SIM_TODAY=2026-05-31                       # 재현 기준일(고정 권장)
```
```bash
pip install -r requirements.txt   # loguru·aiokafka·MSK IAM signer·pandas 등
```
> ⚠️ MSK Serverless는 **클러스터 VPC 안 + 보안그룹 9098 허용된 호스트**(예: 같은 VPC의 EC2)에서만 접속됩니다. 인증은 IAM(OAUTHBEARER) — 실행 호스트에 적절한 AWS 자격증명/역할 필요.

### 실행 (3단계)
```bash
# ① 데이터 분할 (최초 1회 / 리셋 시 재실행)  — 636 샤드 생성, ~15초
python scripts/prepare_edges.py
#    (옵션) --granularity seller   # 셀러 3,095개 단위

# ② 토픽 생성 후 발행
python scripts/kafka_admin.py --create
python scripts/run.py                              # 전체 발행(TAF 가속)
python scripts/run.py --dry-run --max-events 20000 # 브로커 없이 점검

# ③ 도착 확인
python scripts/consume_check.py --sample 3
#  → [consumed] {'order_events': N1, 'review_created': N2}
```

### 🔄 리셋 (언제든 처음부터)
```bash
python scripts/kafka_admin.py --reset      # 토픽 삭제→재생성 (오프셋 0부터 재처리)
# (선택) 분석 결과 DB도 초기화
psql -h <host> -U postgres -d commerce_ops -c "TRUNCATE review_analysis, daily_category_metrics;"
```

### ♻️ 재현 (항상 동일 결과)
시뮬레이터는 **결정론적**입니다 — `event_id = uuid5(event_type, 자연키)`, `occurred_at = SIM_TODAY 기준 시프트`.
같은 `--sim-today`와 같은 입력 데이터면 **매 실행 동일한 이벤트**가 발행되고, 컨슈머는 `event_id`/`review_id`로 멱등 UPSERT 하므로 몇 번을 재생해도 결과가 같습니다.
```bash
python scripts/kafka_admin.py --reset
python scripts/prepare_edges.py --sim-today 2026-05-31
python scripts/run.py
```

### 📈 대용량 트래픽 실험 (확장성 시연)
```bash
python scripts/run.py --scale 50 --rate 20000        # 점포 ×50, 초당 2만건
python scripts/run.py --shard-count 3 --shard-index 0 # 0/1/2를 머신·컨테이너별로
python scripts/run.py --rate 50000 --loop            # 지속 부하
```
> 컨슈머 병렬성 상한 = 파티션 수(현재 `order_events` 6p). 더 큰 부하는 파티션을 늘리세요. 실험 후 `--reset`으로 정리(과금 주의).
>
> 검증 결과(예): **5,438건 발행 → 5,459건 소비, 에러 0** (MSK Serverless `cj-cluster-edge`, ap-northeast-2).
> 구조: `src/edge_simulator/`(로직 모듈) + `scripts/`(CLI 엔트리). 로그 → `/workspace/app_logs/edge_simulator/`, 테스트 → `pytest tests/edge_simulator`.

---

## 라이선스·데이터

Olist 데이터셋 이용 시 Kaggle 라이선스를 준수합니다. 상세는 [DATA.md](./docs/DATA.md).

---

## 변경 상태

- **데이터 레이어 + 엣지 점포 시뮬레이터(→ AWS MSK) 구현·검증 완료** (2026-05-31). 잔여(Gateway·Agents·Consumers·Airflow·배포)는 후속 일정. 세션별 상세는 [patch_logs/](./patch_logs/).
