# Patch Log — 2026-05-31 · 중간 정리 (실시간 파이프라인 완성) + RAG/Agent 로드맵

## 1. 핵심 상태
- **실시간 경로 edge→MSK→consumers→RDS MySQL: 완성·검증.** (MWAA 아님 — 이벤트 스트리밍)
- **MWAA `cj-airflow`(서울, Airflow 3.2.1, AVAILABLE): DAG 0개(`s3://.../dags/` 비어있음).** 배치 DAG 미구현.
- DB는 docs의 PostgreSQL → **실물 RDS MySQL(ap-southeast-2)** 로 정합 완료.

## 2. 데이터 흐름 현황
```
[EC2 시뮬레이터 636점포] --MSK(IAM)--> review_created
   --> [Review Analyzer] --> commerce_ops.review_analysis (RDS MySQL) + review_analyzed
                          --> [Metric Aggregator] --> commerce_ops.daily_category_metrics + metric_updated
실시간 ✅ 완성    |    배치(MWAA daily DAG) ❌    |    질의(Gateway/Agent) ❌
```

## 3. 구현 현황 (docs 매핑)
| 컴포넌트 (docs) | 상태 |
|---|---|
| 엣지 시뮬레이터 (DATA/KAFKA) | ✅ 636 샤드→MSK, 검증 |
| MSK 토픽 (KAFKA) | ✅ order_events12p·review_created6p·analyzed6p·metric_updated3p(compact)·DLQ |
| Review Analyzer (KAFKA §2.1) | ✅ RDS MySQL, 멱등·DLQ·데드락 재시도 (분석=휴리스틱) |
| Metric Aggregator (KAFKA §2.3) | ✅ RDS MySQL, daily_category_metrics 8,712행 검증 |
| 데이터 계층 (ERD/DATA) | 🟡 olist_raw 8테이블 적재✅ / commerce_ops는 review_analysis·daily_category_metrics만 |
| Usage Logger (KAFKA §2.3) | ❌ |
| AI API Gateway (API.md) | ❌ |
| Multi-Agent + Text-to-SQL (AGENTS.md) | ❌ |
| RAG / Qdrant 적재 | ❌ (Qdrant는 localhost:6333 설치됨, 키 필요) |
| RunPod vLLM 연동 | ❌ (`.../v1`, 키 필요) |
| Redis (ARCH §5.6) | ❌ (ElastiCache 없음) |
| Airflow DAG (AIRFLOW.md) | ❌ (MWAA 비어있음) |
| k6 (LOAD_TEST.md) | ❌ |

검증: 1분 바운드 e2e — 발행 18,154(err 0) → 분석 written=analyzed=18,154(dlq 0) → daily_category_metrics 8,712행(606일×70카테고리). GMV 1위 health_beauty $324k.

## 4. docs ↔ 실물 차이
- DB: PostgreSQL → **MySQL(RDS)** ; AIRFLOW.md `postgres_*` 커넥션도 MySQL로 교체 필요
- LLM: OpenAI/Claude → **RunPod vLLM** (`.../v1`)
- 인프라: Compose 단일노드 → **MSK·RDS·MWAA(관리형)** ; 리전: MSK·MWAA 서울 / RDS 시드니(교차리전)
- 신규: **Qdrant(벡터DB) + RAG** 추가 방향

## 5. 다음 목표 (사용자 지시)
- **edge→kafka→rds→qdrant** 적재 플로우 추가 (RAG용 임베딩 적재)
- **RAG + Agent + LangGraph** 로 docs의 Gateway/Multi-Agent 구현 충족
- RunPod **vLLM**로 실제 LLM 분석/추론

## 6. 남은 작업 로드맵 (요약)
- **선행**: vLLM/Qdrant API 키 → `.env`; 임베딩 모델·Redis 위치 결정; 의존성(qdrant-client/openai/langgraph/fastapi/redis); commerce_ops 잔여 5테이블 MySQL 생성
- **P1 RAG 적재**: Qdrant 컬렉션 + 신규 컨슈머(임베딩→Qdrant upsert, 멱등)
- **P2 vLLM 연동**: LLM 클라이언트 + Review Analyzer LLM 모드 전환
- **P3 Gateway(API.md)**: FastAPI 인증/RateLimit/캐시/usage + /v1/*
- **P4 Multi-Agent(AGENTS.md)**: LangGraph Router/MD/VOC/Insight + Text-to-SQL(MySQL) + Qdrant RAG + vLLM
- **P5 MWAA DAG(AIRFLOW.md)**: daily_commerce_ops_pipeline → S3 배포(MySQL)
- **P6 마무리**: Usage Logger, k6, 배포, 데모

## 7. 커밋
main: 0fe1b2c(시뮬레이터+Day1) · 19e59e1(토픽 파티션/DLQ) · 29119fc(Review Analyzer+--duration) · bc07d79(Metric Aggregator+RDS MySQL)
