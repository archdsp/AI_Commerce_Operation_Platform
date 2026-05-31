# 진행 현황 (PROGRESS)

> AI Commerce Operations Platform — Olist 커머스 데이터 기반 실시간 스트리밍 + RAG + LLM Agent 플랫폼
> 최종 갱신: 2026-05-31

---

## 1. 한눈에 보기

```
[EC2 시뮬레이터: 636 지역 점포]
        │  key=seller_id, JSON 이벤트 (TAF 가속 / 합성복제 / 다중샤드)
        ▼  AWS MSK (IAM, 서울)
  ┌─ review_created ─┬─→ [Review Analyzer] ─→ RDS MySQL: review_analysis ─→ review_analyzed
  │                  │                                                          │
  │                  └─→ [Qdrant Loader] ─→ Qdrant: reviews (임베딩, RAG)        ▼
  │                                                              [Metric Aggregator]
  └─ order_events                                                       │
                                                  RDS MySQL: daily_category_metrics + metric_updated

  (질의 경로) Client → Gateway(FastAPI) → LangGraph(Router→MD/VOC/Insight)
                       ├ Text-to-SQL → RDS MySQL
                       ├ RAG → Qdrant 검색
                       └ RunPod vLLM(Qwen2.5-7B) 추론      ← P3/P4 (미구현)
  (배치) MWAA cj-airflow → daily_commerce_ops_pipeline → daily_category_metrics  ← P5 (미구현)
```

| 단계 | 상태 |
|---|---|
| 실시간 인제스천 (edge→MSK) | ✅ |
| 스트림 처리 → RDS (Review Analyzer, Metric Aggregator) | ✅ |
| RAG 적재 (→ Qdrant) | ✅ |
| LLM(vLLM Qwen2.5-7B) 연동 | ✅ 연결 (분석기 LLM 모드) |
| Gateway / Multi-Agent / RAG-Agent | ❌ (P3/P4) |
| MWAA 일배치 DAG | ❌ (P5, 환경만 준비) |
| Usage Logger / k6 / 배포 | ❌ (P6) |

---

## 2. 외부 자원 (모두 사용자 생성, 연결 검증됨)

| 자원 | 상세 | 연결 |
|---|---|---|
| **MSK** | Serverless `cj-cluster-edge`, 서울(ap-northeast-2), IAM(9098) | ✅ |
| **RDS MySQL** | `cj-rds-database-mysql`, MySQL 8.4, db.m5.large, **시드니(ap-southeast-2)** | ✅ (SG에 EC2 IP 허용) |
| **MWAA** | `cj-airflow`, Airflow 3.2.1, mw1.small, 서울 | 🟡 환경만 (DAG 0) |
| **Qdrant** | localhost:6333 v1.18.1, 컬렉션 `reviews`(384/Cosine) | ✅ |
| **vLLM** | RunPod 프록시, **Qwen/Qwen2.5-7B-Instruct** | ✅ (Cloudflare 회피 UA 필요) |

> ⚠️ **교차리전**: MSK·MWAA 서울 ↔ RDS 시드니 (데모용; 운영은 동일 리전 권장)
> ⚠️ **vLLM**: RunPod 프록시가 Cloudflare 뒤 → 브라우저 User-Agent 없으면 error 1010. `common/llm.py`가 UA 강제.

---

## 3. 구현 완료 컴포넌트

### 3.1 엣지 점포 시뮬레이터
- **데이터 분할**(`scripts/prepare_edges.py`): Olist → **636 지역(state/city) 샤드** `data/edges/*.jsonl` + manifest. 무거운 조인 1회만(벡터화), 결정론적 event_id.
- **프로듀서**(`scripts/run.py` + `src/edge_simulator/producer.py`): 샤드 → MSK 발행. `--taf/--rate/--scale/--shard-index/--loop/--duration/--dry-run`. key=seller_id.
- 검증: 실제 MSK 발행 다회 (err 0), dry-run 21만 이벤트.

### 3.2 MSK 토픽 (`scripts/kafka_admin.py`)
`order_events`(12p) · `review_created`(6p) · `review_analyzed`(6p) · `metric_updated`(3p, compact) · `*.dlq`(3p). 생성/리셋/목록, MSK IAM.

### 3.3 데이터 계층 (RDS MySQL)
- `db/schema/mysql/{olist_raw,commerce_ops}.sql` (Postgres→MySQL 포팅), `scripts/setup_mysql.py` 적재.
- 적재: order_items 112,650 · orders 99,441 · products 32,951 · reviews 98,410 등.
- commerce_ops: `review_analysis`, `daily_category_metrics` (나머지 5테이블은 Gateway/Agent 단계).

### 3.4 스트림 컨슈머
- **Review Analyzer**(`src/consumers/review_analyzer.py`): review_created → 감성/VOC 분석 → `review_analysis` 멱등 UPSERT → review_analyzed. 데드락 재시도·DLQ·`--duration`. 분석기: 휴리스틱(기본) / **LLM(Qwen)**.
- **Metric Aggregator**(`src/consumers/metric_aggregator.py`): review_analyzed → 서버사이드 교차스키마 집계 → `daily_category_metrics` UPSERT + metric_updated(변경분만).
- **Qdrant Loader**(`src/consumers/qdrant_loader.py`): review_created → 임베딩 → Qdrant `reviews` upsert.

### 3.5 RAG / LLM 공용
- `src/common/db.py` (MySQL + 데드락 재시도), `src/common/embeddings.py` (fastembed 다국어 MiniLM-L12, 384d), `src/common/llm.py` (vLLM OpenAI호환, UA 우회).

### 3.6 공통
- `src/edge_simulator/`(모듈) + `scripts/`(엔트리) 분리, **loguru** → `/workspace/app_logs/{app}/`, **pytest 23 통과**, `docs/setup/` 가이드, `patch_logs/`.

---

## 4. 검증 기록 (실제 인프라)
| 항목 | 결과 |
|---|---|
| Olist → RDS MySQL 적재 | 8테이블, order_items 112,650 등 |
| state/city 노드 | 636 (DB·시뮬레이터 일치) |
| 1분 e2e (발행→분석→집계) | 발행 18,154(err 0) → 분석 written=analyzed=18,154(dlq 0) → daily_category_metrics 8,712행(606일×70카테고리) |
| GMV 상위 | health_beauty · sports_leisure · watches_gifts … |
| RAG 적재/검색 | 재적재로 **Qdrant reviews 6,000 통일 벡터**(다국어), KO↔PT 의미검색 정상 |
| vLLM | Qwen2.5-7B chat·JSON 분류 동작 |

---

## 5. 남은 작업 (로드맵)
- **P3 Gateway**(API.md): FastAPI 인증/RateLimit/캐시(Redis)/usage + `/v1/*`
- **P4 Multi-Agent + RAG**(AGENTS.md): LangGraph Router→MD/VOC/Insight + Text-to-SQL(MySQL) + RAG(Qdrant) + vLLM ← **핵심**
- **P5 MWAA DAG**(AIRFLOW.md): `daily_commerce_ops_pipeline`(MySQL) S3 배포 (+ 사용자 `dags/reviews_embedding_dag.py` 임베딩 DAG)
- **P6**: Usage Logger · k6 · 배포(Fargate/EKS) · 데모
- 튜닝: LLM sentiment 프롬프트(점수 하이브리드), fastembed 버전 고정, commerce_ops 잔여 테이블

---

## 6. 실행 방법 (요약)
```bash
pip install -r requirements.txt
cp .env.example .env   # MSK/RDS/Qdrant/vLLM 값 채우기 (비밀은 gitignore)

# 데이터 계층
bash scripts/setup_db.sh           # (로컬 PG) 또는
python scripts/setup_mysql.py      # RDS MySQL 스키마+적재

# 토픽
python scripts/kafka_admin.py --create

# 시뮬레이터 (1분만)
python scripts/prepare_edges.py
python scripts/run.py --duration 60

# 컨슈머 (각 1분)
python scripts/review_analyzer.py --duration 60
python scripts/metric_aggregator.py --duration 60
python scripts/qdrant_loader.py --duration 60

# RAG 재적재
python scripts/reload_qdrant.py --limit 6000

# 테스트
pytest tests
```
- 로그: `/workspace/app_logs/{app}/` · 상세 설계: `docs/`, 세션 기록: `patch_logs/`

---

## 7. 커밋 이력 (main)
| 커밋 | 내용 |
|---|---|
| 0fe1b2c | 시뮬레이터 + Day1 데이터레이어 |
| 19e59e1 | 토픽 파티션/압축/DLQ + MSK 재생성 |
| 29119fc | Review Analyzer + --duration |
| bc07d79 | Metric Aggregator + RDS MySQL |
| 34f571b | Qdrant Loader (RAG 적재) |
| f267a04 | 임베딩 모델·NS 배치경로와 통일 |
| 2004423 | vLLM(Qwen2.5-7B) 클라이언트 (Cloudflare UA) |
