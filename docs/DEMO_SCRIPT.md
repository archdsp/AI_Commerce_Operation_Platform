> **상태:** 구현 반영(REALIGNED) — 실제 스택: RDS MySQL · MSK(IAM) · MWAA · RunPod vLLM(Qwen2.5-7B) · Qdrant · AWS API Gateway. 본 문서의 PostgreSQL/Redis/Docker Compose/OpenAI·Claude 언급은 구현과 다름 — 스택 매핑·완성도는 [PROGRESS.md](../PROGRESS.md) 참조.

# 데모 스크립트 (5~10분)

| 항목 | 내용 |
|------|------|
| 문서 버전 | 2.0 |
| 작성일 | 2026-05-31 |
| 대상 | MD → CS(VOC) → 운영(Operations) |
| 사전 준비 | [DEPLOYMENT.md](./DEPLOYMENT.md) 스택 기동, `SIM_TODAY=2026-05-31`, API Key 시드, [../PROGRESS.md](../PROGRESS.md) 완성도 확인 |

> **실제 스택 요약:** 요청은 **AWS API Gateway(REST)** 를 거쳐(API Key + Usage Plan throttle, `X-Origin-Secret` 주입) FastAPI Gateway(`src/gateway/app.py`)로 전달된다. LLM은 **RunPod vLLM Qwen2.5-7B**, DB는 **RDS MySQL**, 리뷰 스트림은 **AWS MSK**, RAG는 **Qdrant**.
> **응답 지연 현실:** `/v1/chat` 실측 **~7~16s** (LLM + Text-to-SQL). 데모 시 로딩 멘트로 자연스럽게 처리.
> **캐시 미구현:** 응답에 `cached` 필드 없음 — "캐시 hit" 데모는 하지 않는다.

---

## 1. 데모 흐름 개요

| 시간 | 페르소나 | 액션 | 포인트 |
|------|----------|------|--------|
| 0:00 | — | 인프라 한 줄 소개 | API Gateway · FastAPI · vLLM · MSK · MWAA |
| 1:00 | MD | 카테고리별 매출 상위 질의 | Text-to-SQL + 집계 |
| 3:30 | CS(VOC) | 배송 부정 리뷰 요약 | Qdrant RAG + 리뷰 분석 |
| 6:00 | 운영 | 매출 인사이트 질의 | `daily_category_metrics` 집계 |
| 8:00 | 플랫폼 | Usage / 모델 / 거버넌스 | `/v1/usage`, `/v1/models` |
| 9:00 | — | 마무리 | 로드맵·미구현 항목 |

---

## 2. 오프닝 (30초)

**멘트 (한국어):**

> Olist 커머스 데이터 위에 AI API Gateway와 MD·VOC·Insight Agent를 올린 운영 플랫폼입니다. 외부 트래픽은 AWS API Gateway가 받아 인증·throttle를 처리하고, 통과한 요청을 FastAPI 백엔드로 넘깁니다. 자연어로 질문하면 SQL 생성·RDS MySQL 조회·LLM(RunPod vLLM Qwen2.5-7B) 요약까지 한 번에 처리하고, 리뷰는 AWS MSK 스트림으로, 일별 KPI는 MWAA(Airflow)로 분리합니다.

**화면:** Architecture 다이어그램 ([ARCHITECTURE.md](./ARCHITECTURE.md)) 또는 `GET /health` 응답.

```http
GET /health
```
응답: `{ "status": "ok" }` — (참고: `/ready`는 없음)

---

## 3. MD 페르소나 (약 2분)

### 3.1 질의 — 카테고리별 매출 상위

```http
POST /v1/chat
X-API-Key: <demo_md_key>
Content-Type: application/json

{
  "query": "카테고리별 매출 상위 알려줘",
  "session_id": "demo-md-001"
}
```

> AWS API Gateway 경유 시: API Gateway가 자체 **API Key**로 인증·throttle 후 백엔드에 `X-Origin-Secret`을 주입한다. 위 `X-API-Key`는 FastAPI Gateway가 `commerce_ops.api_keys`(sha256)로 검증하는 키.

### 3.2 기대 응답 (실제 스키마)

```json
{
  "agent_type": "md",
  "answer": "카테고리별 GMV 상위는 health_beauty(약 324K), sports_leisure, watches_gifts, computers_accessories, auto 순입니다…",
  "sql": "SELECT category_en, SUM(gmv) AS gmv FROM daily_category_metrics GROUP BY category_en ORDER BY gmv DESC LIMIT 5",
  "rows_count": 5,
  "model": "Qwen/Qwen2.5-7B-Instruct",
  "latency_ms": 11000
}
```

> 실제 데이터: `daily_category_metrics` 의 `SUM(gmv)` 기준 1위는 **health_beauty ≈ 324K**, 이어 **sports_leisure · watches_gifts · computers_accessories · auto**.

### 3.3 멘트

> MD는 카테고리·SKU 매출을 자연어로 묻습니다. Gateway가 자연어를 SQL로 변환(Text-to-SQL)하고 RDS MySQL에서 집계한 뒤 vLLM이 한국어로 요약합니다. 응답에 실행된 `sql`과 `latency_ms`가 함께 반환됩니다.

> **참고:** LLM+조회 경로라 1회 응답이 **수 초~십수 초(~7~16s)** 걸립니다. 캐시 계층은 아직 **미구현(계획)** 입니다 — [LOAD_TEST.md](./LOAD_TEST.md), [../TODO.md](../TODO.md).

---

## 4. CS(VOC) 페르소나 (약 2.5분)

### 4.1 질의 — 배송 부정 리뷰

```http
POST /v1/agent/run
X-API-Key: <demo_cs_key>
Content-Type: application/json

{
  "agent_type": "voc",
  "query": "배송 관련 부정 리뷰 요약해줘"
}
```

### 4.2 기대 응답 (실제 스키마)

```json
{
  "agent_type": "voc",
  "answer": "배송 관련 부정 리뷰 약 20건을 분석했습니다. 주요 불만은 배송 지연·미수령이며…(요약)",
  "sql": "SELECT review_id, review_score, review_comment FROM ... WHERE ... score<=2 AND ...delivery...",
  "rows_count": 20,
  "latency_ms": 13000
}
```

> 실제 동작: 배송 VOC 질의는 **부정 배송 리뷰 약 20건**을 조회하고 **Qdrant RAG**로 관련 리뷰를 검색해 요약을 생성한다.

### 4.3 멘트

> VOC Agent는 리뷰 텍스트를 Qdrant에 임베딩해두고, 질문과 의미가 가까운 리뷰를 검색(RAG)한 뒤 vLLM이 핵심 불만을 요약합니다. 신규 리뷰는 AWS MSK 스트림으로 들어와 Review Analyzer가 감성·VOC 카테고리를 붙입니다.

### 4.4 (선택) MSK 리뷰 한 건

> 리뷰 이벤트 1건을 AWS MSK 토픽에 발행 → Review Analyzer 처리 후 동일 질의 재실행 → 반영 확인.
> (스트리밍 파이프 상세: [KAFKA.md](./KAFKA.md))

---

## 5. 운영(Operations) 페르소나 (약 2분)

### 5.1 질의 — 매출 인사이트

```http
POST /v1/agent/run
X-API-Key: <demo_ops_key>
Content-Type: application/json

{
  "agent_type": "insight",
  "query": "최근 카테고리 매출 흐름과 시사점 알려줘"
}
```

> `model` 필드를 요청에 넣지 않는다 — 모델은 백엔드 고정(RunPod vLLM Qwen2.5-7B). (이전 초안의 `"model": "claude-3-5-sonnet"`은 구현과 무관하여 제거)

### 5.2 기대 응답 (실제 스키마)

```json
{
  "agent_type": "insight",
  "answer": "## 요약\nhealth_beauty가 GMV를 견인(약 324K)하며 sports_leisure·watches_gifts가 뒤를 잇습니다. …시사점·권고…",
  "sql": "SELECT category_en, SUM(gmv) ... FROM daily_category_metrics ...",
  "rows_count": 5,
  "latency_ms": 12000
}
```

> Insight Agent의 응답도 상위 5개 응답 필드(`agent_type`, `answer`, `sql`, `rows_count`, `latency_ms`)로 동일하게 반환된다. (별도 `report` 중첩 객체는 현재 스키마에 없음)

### 5.3 멘트

> Insight Agent는 MWAA(Airflow)가 매일 적재한 `daily_category_metrics`를 봅니다. 실시간 Agent와 배치 집계를 분리해 응답 품질과 비용을 맞췄습니다.

**화면 (선택):** MWAA(Airflow) UI에서 일별 파이프라인 성공 run.

---

## 6. 플랫폼·거버넌스 (약 1분)

```http
GET /v1/usage
X-API-Key: <demo_ops_key>
```

기대 응답 (실제 스키마):

```json
{
  "total_requests": 42,
  "avg_latency_ms": 10850.0,
  "by_endpoint": { "/v1/chat": 20, "/v1/agent/run": 18, "/v1/sql/generate": 4 },
  "model_calls": 38
}
```

**멘트:** 엔드포인트별 요청 수·평균 지연·모델 호출 수를 집계합니다. 외부 throttle(Rate Limit)은 **AWS API Gateway Usage Plan**에서 관리합니다.

```http
GET /v1/models
X-API-Key: <demo_ops_key>
```
응답: `{ "data": [{ "id": "Qwen/Qwen2.5-7B-Instruct", "provider": "runpod" }] }`

---

## 7. 클로징 (30초)

> 데모 흐름: MD 매출 → VOC 배송 리뷰 → 운영 인사이트 → 거버넌스까지 한 게이트웨이에서 처리했습니다. 앞으로는 **응답 캐시 도입**과 **k6 부하 테스트(현재 미구현·계획, P2)** 로 P95·처리량을 검증할 예정입니다. 계획·진행은 [../TODO.md](../TODO.md), [../PROGRESS.md](../PROGRESS.md)에 정리되어 있습니다.

---

## 8. 데모 실패 시 플랜 B

| 문제 | 대체 |
|------|------|
| RunPod vLLM 장애/지연 | 사전 캡처한 응답 JSON 사용 |
| Agent 응답 과지연 | `POST /v1/sql/generate`로 SQL+rows만 시연 |
| Qdrant/RAG 이슈 | `review_analysis` 직접 COUNT/SELECT 쿼리 |
| AWS MSK lag | 스트리밍 단계 생략, 적재된 리뷰로 질의 |

```http
POST /v1/sql/generate
X-API-Key: <demo_md_key>
Content-Type: application/json

{ "query": "카테고리별 매출 상위 5개" }
```
응답: `{ "sql": "...", "rows": [...], "rows_count": 5, "latency_ms": 9000 }`

---

## 9. 체크리스트

- [ ] API Key 3종 (md/cs/ops) `commerce_ops.api_keys` 시드 (sha256)
- [ ] AWS API Gateway API Key + Usage Plan, `GATEWAY_ORIGIN_SECRET` 설정
- [ ] `daily_category_metrics` 적재 확인 (health_beauty 등)
- [ ] `review_analysis` / Qdrant 컬렉션 적재 (배송 부정 리뷰 포함)
- [ ] RunPod vLLM(Qwen2.5-7B) 엔드포인트 헬스 확인
- [ ] `SIM_TODAY=2026-05-31` 고정
- [ ] 화면 녹화 1080p (응답 지연 ~7~16s 감안한 편집)

---

## 10. 변경 이력

| 버전 | 날짜 | 변경 |
|------|------|------|
| 2.0 | 2026-05-31 | REALIGNED — 실제 스택/엔드포인트 반영 |
| 1.0 | 2026-05-31 | 데모 스크립트 초안 |
