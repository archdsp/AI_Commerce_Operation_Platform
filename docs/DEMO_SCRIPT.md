> **상태:** 구현 반영(REALIGNED) — 실제 스택: RDS MySQL · MSK(IAM) · MWAA · RunPod vLLM(Qwen2.5-7B) · Qdrant · AWS API Gateway. 본 문서의 PostgreSQL/Redis/Docker Compose/OpenAI·Claude 언급은 구현과 다름 — 스택 매핑·완성도는 [PROGRESS.md](../PROGRESS.md) 참조.

# 데모 스크립트 (5~10분)

| 항목 | 내용 |
|------|------|
| 문서 버전 | 1.0 |
| 작성일 | 2026-05-31 |
| 대상 | MD → CS → 운영 (Operations) |
| 사전 준비 | [DEPLOYMENT.md](./DEPLOYMENT.md) 스택 기동, `SIM_TODAY=2026-05-31`, API Key |

---

## 1. 데모 흐름 개요

| 시간 | 페르소나 | 액션 | 포인트 |
|------|----------|------|--------|
| 0:00 | — | 인프라 한 줄 소개 | Gateway·Agent·Kafka·Airflow |
| 1:00 | MD | 매출 감소 상품 질의 | Text-to-SQL + 인사이트 |
| 3:00 | CS | 부정 리뷰·VOC | review_analysis |
| 5:00 | 운영 | 매출 감소 원인 | Insight 리포트 |
| 7:00 | 플랫폼 | Usage·Cache·Rate Limit | `/v1/usage` |
| 8:00 | (선택) | Kafka 리뷰 1건 | 실시간 파이프 |
| 9:00 | — | 마무리 | KPI 목표 언급 |

---

## 2. 오프닝 (30초)

**멘트 (한국어):**

> Olist 커머스 데이터 위에 AI API Gateway와 MD·VOC·Insight Agent를 올린 운영 플랫폼입니다. 자연어로 질문하면 SQL 생성·DB 조회·LLM 요약까지 한 번에 처리하고, 리뷰는 Kafka로, 일별 KPI는 Airflow로 분리합니다.

**화면:** Architecture 다이어그램 ([ARCHITECTURE.md](./ARCHITECTURE.md)) 또는 `docker compose ps`

---

## 3. MD 페르소나 (약 2분)

### 3.1 질의

```http
POST /v1/chat
X-API-Key: <demo_md_key>
Content-Type: application/json

{
  "query": "이번 달 판매량이 감소한 상품 알려줘",
  "session_id": "demo-md-001"
}
```

### 3.2 기대 응답 형태

```json
{
  "cached": false,
  "data": {
    "agent_type": "md",
    "answer": "시뮬레이션 기준일(2026-05-31) 대비 전월 판매량이 감소한 상품…",
    "insights": ["카테고리 X에서 감소 폭 최대", "..."],
    "tables": [{
      "name": "declining_products",
      "columns": ["product_id", "category_en", "gmv_delta_pct"],
      "rows": [["...", "health_beauty", -18.2]]
    }],
    "metadata": { "prompt_version": "md-v1.0.0", "latency_ms": 5000 }
  }
}
```

### 3.3 멘트

> MD는 카테고리·SKU 매출을 자연어로 묻습니다. 첫 호출은 Agent 경로이고, 같은 질문을 반복하면 Redis 캐시로 P95 300ms 이하를 노립니다.

### 3.4 (선택) 캐시 데모

동일 요청 2회 → `"cached": true`, `latency_ms` 급감.

---

## 4. CS 페르소나 (약 2분)

### 4.1 질의

```http
POST /v1/agent/run
X-API-Key: <demo_cs_key>

{
  "agent_type": "voc",
  "query": "최근 부정 리뷰가 증가한 상품 알려줘"
}
```

### 4.2 기대 응답 형태

```json
{
  "data": {
    "agent_type": "voc",
    "answer": "최근 7일(sim) 부정 리뷰가 전주 대비 증가한 상품 Top 5…",
    "insights": [
      "배송 지연 VOC가 40% 차지",
      "product_id ABC123 부정 리뷰 +15건"
    ],
    "tables": [{
      "name": "voc_spike_products",
      "columns": ["product_id", "negative_count", "top_voc_category"],
      "rows": [["ABC123", 15, "delivery"]]
    }]
  }
}
```

### 4.3 멘트

> VOC Agent는 Kafka로 채워진 `review_analysis`를 우선 사용합니다. 리뷰가 들어오면 Review Analyzer가 감성·VOC 카테고리를 붙입니다.

### 4.4 (선택) Kafka 한 건

터미널에서 `review_created` 1건 발행 → 수 초 후 동일 상품 질의 재실행 → 카운트 증가 확인.

---

## 5. 운영(Operations) 페르소나 (약 2분)

### 5.1 질의

```http
POST /v1/chat
X-API-Key: <demo_ops_key>

{
  "query": "매출 감소 원인 분석해줘",
  "model": "claude-3-5-sonnet-20241022"
}
```

### 5.2 기대 응답 형태

```json
{
  "data": {
    "agent_type": "insight",
    "answer": "## Executive Summary\n전월 대비 GMV -12%…",
    "insights": [],
    "tables": [],
    "metadata": {
      "report": {
        "findings": ["카테고리 A GMV -20%", "부정 리뷰 증가와 상관"],
        "root_causes": ["배송 SLA 악화", "프로모션 종료"],
        "recommended_actions": ["배송 파트너 리뷰", "카테고리 A 프로모션"]
      }
    }
  }
}
```

> **TODO (구현):** `report` 객체를 `data` top-level로 고정할지 스키마 확정.

### 5.3 멘트

> Insight Agent는 Airflow가 매일 적재한 `daily_category_metrics`를 봅니다. 실시간 Agent와 배치 집계를 분리해 응답 품질을 맞췄습니다.

**화면 (선택):** Airflow UI `daily_commerce_ops_pipeline` 성공 run.

---

## 6. 플랫폼·거버넌스 (약 1분)

```http
GET /v1/usage?from=2026-05-24&to=2026-05-31
X-API-Key: <demo_ops_key>
```

**멘트:** API Key별 토큰·비용·캐시 hit ratio. Rate Limit 100 req/min.

```http
GET /v1/models
```

---

## 7. 클로징 (30초)

> k6로 500~1,000 VU, Agent P95 10초, 캐시 hit 30% 이상을 검증 예정입니다. 문서는 `docs/`에 ERD·API·Kafka·Airflow까지 사전 정의되어 있습니다.

---

## 8. 데모 실패 시 플랜 B

| 문제 | 대체 |
|------|------|
| LLM 장애 | 사전 녹화 응답 JSON |
| Agent timeout | `POST /v1/sql/generate` only |
| Kafka lag | `review_analysis` 직접 COUNT 쿼리 |

> **TODO:** 플랜 B JSON `demo/fixtures/` 저장.

---

## 9. 체크리스트

- [ ] API Key 3종 (md/cs/ops) 시드
- [ ] `daily_category_metrics` 최소 30일 (**TODO:** backfill)
- [ ] `review_analysis` 1만건+
- [ ] curl/httpie 스크립트 `demo/run.sh`
- [ ] 화면 녹화 1080p

---

## 10. 변경 이력

| 버전 | 날짜 | 변경 |
|------|------|------|
| 1.0 | 2026-05-31 | 데모 스크립트 초안 |
