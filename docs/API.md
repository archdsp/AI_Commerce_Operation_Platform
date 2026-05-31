> **상태:** 구현 반영(REALIGNED) — 실제 스택: RDS MySQL · MSK(IAM) · MWAA · RunPod vLLM(Qwen2.5-7B) · Qdrant · AWS API Gateway. 본 문서의 PostgreSQL/Redis/Docker Compose/OpenAI·Claude 언급은 구현과 다름 — 스택 매핑·완성도는 [PROGRESS.md](../PROGRESS.md) 참조.

# REST API 명세

| 항목 | 내용 |
|------|------|
| 문서 버전 | 2.0 |
| Base URL | `http://localhost:8000` (FastAPI 직접) · 운영은 AWS API Gateway(REST) 경유 |
| 작성일 | 2026-05-31 |
| 구현 | `src/gateway/app.py` (FastAPI, `version="0.1.0"`) |
| OpenAPI | FastAPI 자동 생성(`/openapi.json`, `/docs`). 정적 export는 **미구현([TODO.md](../TODO.md))** |

> **이 문서의 "현재 구현"은 `src/gateway/app.py`의 실제 응답과 일치한다.** 향후 확장(JWT, Redis 캐시, 풍부한 응답 래퍼 등)은 모두 **미구현/계획**으로 명시한다.

---

## 0. 아키텍처 (요청 흐름)

```text
Client ──X-API-Key──▶ AWS API Gateway(REST) ──X-Origin-Secret 주입──▶ FastAPI Gateway(app.py) ──▶ Agent/LLM/MySQL
                      (Usage Plan = throttle/quota)        (verify_origin 미들웨어로 직접 접근 차단)
```

- **AWS API Gateway(REST)** 가 FastAPI 앞단에 위치 — 인프라: `infra/terraform/api-gateway/`. Usage Plan으로 throttle/quota를 관리형 처리하고, 통과한 요청에 `X-Origin-Secret` 헤더를 주입한다.
- **FastAPI Gateway**(`src/gateway/app.py`)는 `GATEWAY_ORIGIN_SECRET` 환경 변수가 설정되면 `/v1/*` 요청에 대해 `X-Origin-Secret` 일치를 검사(`verify_origin` 미들웨어, 불일치 시 `403`). 미설정 시 로컬 개발용으로 검증을 생략한다.

---

## 1. 공통 규칙

### 1.1 인증

| 방식 | 헤더 | 상태 |
|------|------|------|
| API Key | `X-API-Key: <plain_key>` | **현재 구현** — `sha256(key)` → `commerce_ops.api_keys.key_hash` 조회, `is_active=1` 검증 |
| JWT | `Authorization: Bearer <jwt>` | **미구현(계획)** — [TODO.md](../TODO.md) |

- `X-API-Key` 누락 시 `401` (`detail: "X-API-Key 헤더 필요"`), 일치 키 없음 시 `401` (`detail: "유효하지 않은 API Key"`).
- 검증 통과 시 `api_keys.id`를 호출 식별자로 사용해 `agent_requests` / `agent_executions` / `model_usage_logs`에 로깅한다.
- JWT(HS256, `sub`/`team` claim)는 **미구현** — 현재 인증 수단은 API Key 단일이다.

### 1.2 Rate Limit

| 항목 | 내용 |
|------|------|
| 처리 위치 | **AWS API Gateway Usage Plan** (관리형 throttle/quota). 앱 내부 구현 아님 |
| 인프라 | `infra/terraform/api-gateway/` |
| 초과 응답 | API Gateway 표준 `429` (Usage Plan 한도 초과) |
| 앱 내 Redis 카운터 | **미구현** — 기존 `ratelimit:{principal}:{...}` Redis 설계는 폐기/계획 |

> 한도값(예: req/min, quota/day)은 Usage Plan 설정에 종속된다. FastAPI 앱은 Rate Limit 로직을 갖지 않는다.

### 1.3 캐시

| 항목 | 내용 |
|------|------|
| 질의 해시 캐시(`POST /v1/chat`·`/v1/agent/run`) | **미구현(계획)** — [TODO.md](../TODO.md) |
| Redis 캐시(`cache:v1:{sha256(...)}`, `CACHE_TTL_SECONDS`) | **미구현** — Redis 미사용 |
| API Gateway 경로 캐시 | POST 본문(body)을 키로 사용할 수 없어 `/v1/chat` 등 동일 질의 캐시에 부적합. 따라서 응답에 `cached` 필드를 두지 않음 |

- 현재 모든 응답은 캐시 표시(`cached`) 필드를 **포함하지 않는다.** 도입 시 응답 형태가 변경될 수 있다(아래 §1.5 향후 계획 참조).

### 1.4 공통 헤더

| 헤더 | 필수 | 상태 / 설명 |
|------|------|------|
| `X-API-Key` | Y(`/v1/*`) | 인증 (§1.1) |
| `Content-Type` | POST | `application/json` |
| `X-Origin-Secret` | — | **API Gateway가 주입** — 클라이언트가 직접 설정하지 않음. 직접 호출 차단용 |
| `X-Request-Id` | — | **미구현** — 현재 응답/로그에 echo하지 않음. 요청 ID(UUID)는 서버가 내부 로깅용으로만 생성 |
| `X-Session-Id` | — | **미구현** — `POST /v1/chat`의 `session_id` 필드는 수신하나(아래 §2) 현재 세션 이력 저장/활용 없음 |

### 1.5 응답 형태

**현재 구현:** 모든 엔드포인트는 **평면(flat) JSON 객체**를 반환한다. `request_id` / `cached` / `data` 래퍼는 **없다.** 각 엔드포인트의 정확한 형태는 §2~§6 참조.

**오류 응답(현재 구현):** FastAPI 기본 형태로 `detail` 문자열만 반환한다.

```json
{ "detail": "유효하지 않은 API Key" }
```

> **향후 계획(미구현):** `{request_id, cached, data:{...}}` 형태의 풍부한 래퍼 및 `{error:{code,message,details}}` 구조화 오류는 [TODO.md](../TODO.md)에 등재. 현재 스펙은 평면 응답이 정본이다.

### 1.6 HTTP 상태 코드 (현재 구현)

| HTTP | 발생 위치 | 설명 |
|------|----------|------|
| 200 | 전 엔드포인트 | 성공 |
| 400 | `/v1/agent/run` | `agent_type`이 `md`/`voc`/`insight`가 아님 |
| 400 | `/v1/sql/generate` | Text-to-SQL 가드레일 거부/실패(`SQLRejected`) — `detail: "SQL 거부/실패: ..."` |
| 401 | `require_key` | `X-API-Key` 누락 또는 무효 |
| 403 | `verify_origin` | `GATEWAY_ORIGIN_SECRET` 설정 시 `X-Origin-Secret` 불일치(직접 접근) |
| 422 | FastAPI | 요청 본문 스키마 위반(Pydantic 검증) |
| 429 | AWS API Gateway | Usage Plan 한도 초과(§1.2, 앱 외부) |

> **미구현/계획:** 구조화 에러 코드(`SQL_REJECTED`, `RATE_LIMIT_EXCEEDED`, `AGENT_TIMEOUT`, `LLM_PROVIDER_ERROR` 등)와 `503` 타임아웃은 [TODO.md](../TODO.md) 참조. LLM은 RunPod vLLM(OpenAI 호환)이며 OpenAI/Claude가 아님.

---

## 2. POST /v1/chat

일반 자연어 질의. Agent Router(`agents.graph.answer_query`)가 MD/VOC/Insight 중 자동 선택한다.

### Request

```json
{
  "query": "이번 달 판매량이 감소한 상품 알려줘",
  "session_id": "sess-demo-001"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `query` | string | Y | 자연어 질의 |
| `session_id` | string | N | 수신하나 현재 미사용(세션 이력 **미구현**) |

> `model` / `options.*` 필드는 **미구현** — 요청 모델은 서버 고정(RunPod vLLM `Qwen/Qwen2.5-7B-Instruct`).

### Response 200 (현재 구현)

```json
{
  "agent_type": "md",
  "answer": "이번 달(sim) 기준 판매량이 전월 대비 감소한 상품 Top 10은 ...",
  "sql": "SELECT ...",
  "rows_count": 10,
  "model": "Qwen/Qwen2.5-7B-Instruct",
  "latency_ms": 4520
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `agent_type` | string | 라우터가 선택한 에이전트(`md`/`voc`/`insight`) |
| `answer` | string | 자연어 답변 |
| `sql` | string\|null | 생성·실행된 SQL(없으면 `null`) |
| `rows_count` | int | SQL 결과 행 수 |
| `model` | string | 사용 모델(`DEFAULT_MODEL`) |
| `latency_ms` | int | 처리 시간(ms) |

> `insights` / `tables` / `metadata` / `cached` 등 풍부한 필드는 **미구현(계획)**.

---

## 3. POST /v1/agent/run

특정 Agent 강제 실행.

### Request

```json
{
  "agent_type": "voc",
  "query": "최근 부정 리뷰가 증가한 상품 알려줘"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `agent_type` | string | Y | `md` / `voc` / `insight` (그 외 값은 `400`) |
| `query` | string | Y | 자연어 질의 |

| `agent_type` | 설명 |
|--------------|------|
| `md` | MD Agent |
| `voc` | VOC Agent |
| `insight` | Insight Agent |

### Response 200 (현재 구현)

`/v1/chat`과 유사하나 **`model` 필드가 없다.** `agent_type`은 요청값과 일치한다.

```json
{
  "agent_type": "voc",
  "answer": "...",
  "sql": "SELECT ...",
  "rows_count": 8,
  "latency_ms": 3110
}
```

---

## 4. POST /v1/sql/generate

Text-to-SQL 수행 — SQL 생성과 실행을 함께 수행하고 결과 일부를 반환한다(`agents.text_to_sql.run_sql`).

### Request

```json
{
  "query": "카테고리별 매출 순위 상위 10개"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `query` | string | Y | 자연어 질의 |

> `execute` / `database` 필드는 **미구현** — 현재 항상 실행하며 대상 DB는 서버 설정(`commerce_ops`/`olist_raw`)에 종속.

### Response 200 (현재 구현)

```json
{
  "sql": "SELECT category_name_en, SUM(gmv) AS gmv\nFROM ...\nGROUP BY 1\nORDER BY 2 DESC\nLIMIT 10",
  "rows": [["health_beauty", 125000.50]],
  "rows_count": 10,
  "latency_ms": 980
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `sql` | string | 생성·실행된 SQL |
| `rows` | array | 결과 행 — **최대 50행**(`rows[:50]`)으로 잘림 |
| `rows_count` | int | 전체 결과 행 수(자르기 전) |
| `latency_ms` | int | 처리 시간(ms) |

### Response 400 (가드레일 거부)

가드레일(`agents.sql_guard.SQLRejected`) 위반 시:

```json
{ "detail": "SQL 거부/실패: Forbidden keyword detected: DROP" }
```

가드레일 규칙: [AGENTS.md §Text-to-SQL](./AGENTS.md)

---

## 5. GET /v1/usage

요청 수·평균 지연·엔드포인트별 분포·모델 호출 수 집계(`agent_requests` / `model_usage_logs` 기반).

### Query Parameters

> `from` / `to` / `group_by` 파라미터는 **미구현** — 현재 전체 누적 집계만 반환한다. 기간/그룹 필터는 [TODO.md](../TODO.md).

### Response 200 (현재 구현)

```json
{
  "total_requests": 1240,
  "avg_latency_ms": 3820.5,
  "by_endpoint": {
    "/v1/chat": 900,
    "/v1/agent/run": 240,
    "/v1/sql/generate": 100
  },
  "model_calls": 1240
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `total_requests` | int | `agent_requests` 총 건수 |
| `avg_latency_ms` | float | 평균 지연(ms, 1자리 반올림) |
| `by_endpoint` | object | 엔드포인트별 요청 수 |
| `model_calls` | int | `model_usage_logs` 총 건수 |

> 토큰/비용/캐시 히트(`total_tokens`, `estimated_cost_usd`, `cache_hits`) 및 본인 데이터 한정 조회는 **미구현(계획)**.

---

## 6. GET /v1/models

사용 가능 LLM 목록.

### Response 200 (현재 구현)

```json
{
  "data": [
    { "id": "Qwen/Qwen2.5-7B-Instruct", "provider": "runpod" }
  ]
}
```

- 현재 단일 모델: RunPod vLLM `Qwen/Qwen2.5-7B-Instruct`(OpenAI 호환 API, `provider="runpod"`).
- `gpt-4o-mini` / `claude-3-5-sonnet`, `default_for`, `max_tokens`, `ENABLED_MODELS` 동기화 등은 **미구현(계획)** — [TODO.md](../TODO.md).

---

## 7. 엔드포인트 요약

| Method | Path | 인증 | Rate Limit | Cache |
|--------|------|------|------------|-------|
| POST | `/v1/chat` | X-API-Key | API Gateway Usage Plan | 미구현 |
| POST | `/v1/agent/run` | X-API-Key | API Gateway Usage Plan | 미구현 |
| POST | `/v1/sql/generate` | X-API-Key | API Gateway Usage Plan | 미구현 |
| GET | `/v1/usage` | X-API-Key | API Gateway Usage Plan | 미구현 |
| GET | `/v1/models` | X-API-Key | API Gateway Usage Plan | 미구현 |
| GET | `/health` | 없음 | 없음 | 없음 |

> `/ready`는 **미구현** — 헬스 체크는 `GET /health`(`{"status":"ok"}`) 단일.

---

## 8. 구현 메모 (FastAPI)

현재 Gateway는 단일 모듈로 구현되어 있다.

```text
src/gateway/
└── app.py   # FastAPI 앱: verify_origin 미들웨어, require_key 의존성,
              # /health · /v1/{models,chat,agent/run,sql/generate,usage}, _log() 로깅
```

- 의존 모듈: `agents.graph.answer_query`(라우팅), `agents.text_to_sql.run_sql`, `agents.sql_guard`(가드레일), `common.db`(pymysql → RDS MySQL), `common.llm`(`DEFAULT_MODEL`, RunPod vLLM).
- 모듈 분리(`api/v1/*.py`, `middleware/`, `services/cache.py`) 및 OpenAPI 정적 export는 **미구현(계획)** — [TODO.md](../TODO.md).

---

## 9. 변경 이력

| 버전 | 날짜 | 변경 |
|------|------|------|
| 2.0 | 2026-05-31 | REALIGNED — 실제 스택/응답 반영 |
| 1.0 | 2026-05-31 | API 초안 |
