> **상태:** Draft (Pre-implementation)

# REST API 명세

| 항목 | 내용 |
|------|------|
| 문서 버전 | 1.0 |
| Base URL | `http://localhost:8000` (개발) |
| 작성일 | 2026-05-31 |
| OpenAPI | **TODO (구현 후):** FastAPI 자동 생성 → `openapi.json` export |

---

## 1. 공통 규칙

### 1.1 인증

다음 중 **하나** 필수 (둘 다 있으면 API Key 우선).

| 방식 | 헤더 | 설명 |
|------|------|------|
| API Key | `X-API-Key: <plain_key>` | `api_keys.key_hash` 검증 |
| JWT | `Authorization: Bearer <jwt>` | HS256, `sub`=user_id, `team` claim |

JWT 발급 엔드포인트는 v1 Out of Scope — 개발용 정적 토큰 또는 Admin 스크립트로 생성 (**TODO**).

### 1.2 Rate Limit

| 항목 | 값 |
|------|-----|
| 한도 | **100 requests / minute** per API Key (또는 JWT `sub`) |
| 저장 | Redis `ratelimit:{principal}:{YYYYMMDDHHmm}` |
| 초과 응답 | `429` + `Retry-After` (초) |

### 1.3 캐시

| 항목 | 값 |
|------|-----|
| 저장소 | Redis |
| 키 | `cache:v1:{sha256(normalized_query\|agent\|model)}` |
| TTL | 기본 3600초 (환경 변수 `CACHE_TTL_SECONDS`) |
| 적용 API | `POST /v1/chat`, `POST /v1/agent/run` (동일 질의) |
| 미적용 | `POST /v1/sql/generate`, `GET *` |
| 응답 표시 | `"cached": true/false` |

`normalized_query`: trim, lowercase, 연속 공백 제거.

### 1.4 공통 헤더

| 헤더 | 필수 | 설명 |
|------|------|------|
| `Content-Type` | POST | `application/json` |
| `X-Request-Id` | 선택 | 없으면 서버 UUID 생성, 응답·로그에 echo |
| `X-Session-Id` | 선택 | 대화 이력 (Redis session) |

### 1.5 공통 응답 래퍼

성공 시:

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "cached": false,
  "data": { }
}
```

오류 시:

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Try again in 42 seconds.",
    "details": {}
  }
}
```

### 1.6 HTTP 상태·에러 코드

| HTTP | code | 설명 |
|------|------|------|
| 400 | `INVALID_REQUEST` | JSON 스키마·필드 오류 |
| 401 | `UNAUTHORIZED` | 인증 실패 |
| 403 | `FORBIDDEN` | 비활성 API Key |
| 404 | `NOT_FOUND` | 리소스 없음 |
| 429 | `RATE_LIMIT_EXCEEDED` | Rate Limit |
| 422 | `AGENT_ROUTING_FAILED` | 라우팅 불가 질의 |
| 422 | `SQL_REJECTED` | Text-to-SQL 가드레일 거부 |
| 500 | `INTERNAL_ERROR` | 미처리 예외 |
| 503 | `AGENT_TIMEOUT` | Agent P95 초과 등 (**TODO:** 타임아웃 값 구현 시 확정) |
| 502 | `LLM_PROVIDER_ERROR` | OpenAI/Claude 오류 |

---

## 2. POST /v1/chat

일반 자연어 질의. Agent Router가 `agent_type=auto`로 MD/VOC/Insight 중 선택.

### Request

```json
{
  "query": "이번 달 판매량이 감소한 상품 알려줘",
  "session_id": "sess-demo-001",
  "model": "gpt-4o-mini",
  "options": {
    "language": "ko",
    "max_rows": 50
  }
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `query` | string | Y | 1~4000자 |
| `session_id` | string | N | Redis 세션 |
| `model` | string | N | 기본값 서버 설정 |
| `options.language` | string | N | `ko` / `en` |
| `options.max_rows` | int | N | SQL 결과 상한, 기본 100 |

### Response 200

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "cached": false,
  "data": {
    "agent_type": "md",
    "answer": "이번 달(sim) 기준 판매량이 전월 대비 감소한 상품 Top 10은 다음과 같습니다...",
    "insights": [
      "카테고리 'health_beauty'에서 감소 폭이 가장 큼"
    ],
    "tables": [
      {
        "name": "declining_products",
        "columns": ["product_id", "category_en", "gmv_delta_pct"],
        "rows": [
          ["abc123", "health_beauty", -23.5]
        ]
      }
    ],
    "metadata": {
      "prompt_version": "md-v1.0.0",
      "latency_ms": 4520,
      "rows_returned": 10
    }
  }
}
```

### Response 429

```json
{
  "request_id": "...",
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "100 requests per minute exceeded",
    "details": { "retry_after_seconds": 42 }
  }
}
```

---

## 3. POST /v1/agent/run

특정 Agent 강제 실행.

### Request

```json
{
  "agent_type": "voc",
  "query": "최근 부정 리뷰가 증가한 상품 알려줘",
  "model": "claude-3-5-sonnet-20241022",
  "session_id": null
}
```

| `agent_type` | 설명 |
|--------------|------|
| `md` | MD Agent |
| `voc` | VOC Agent |
| `insight` | Insight Agent |

### Response 200

`/v1/chat`과 동일 구조. `data.agent_type`은 요청값과 일치.

---

## 4. POST /v1/sql/generate

Text-to-SQL만 수행 (실행은 `execute` 플래그로 선택).

### Request

```json
{
  "query": "카테고리별 매출 순위 상위 10개",
  "execute": true,
  "database": "commerce_ops"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `query` | string | Y | |
| `execute` | boolean | N | default `false` |
| `database` | string | N | `commerce_ops` / `olist_raw` |

### Response 200 (execute=false)

```json
{
  "request_id": "...",
  "cached": false,
  "data": {
    "sql": "SELECT category_name_en, SUM(gmv) AS gmv\nFROM daily_category_metrics\nWHERE metric_date >= :sim_month_start\nGROUP BY 1\nORDER BY 2 DESC\nLIMIT 10",
    "validated": true,
    "executed": false
  }
}
```

### Response 200 (execute=true)

```json
{
  "request_id": "...",
  "cached": false,
  "data": {
    "sql": "SELECT ...",
    "validated": true,
    "executed": true,
    "columns": ["category_name_en", "gmv"],
    "rows": [["health_beauty", 125000.50]],
    "row_count": 10
  }
}
```

### Response 422 (가드레일)

```json
{
  "request_id": "...",
  "error": {
    "code": "SQL_REJECTED",
    "message": "Forbidden keyword detected: DROP",
    "details": { "sql_fragment": "DROP TABLE" }
  }
}
```

가드레일: [AGENTS.md §Text-to-SQL](./AGENTS.md)

---

## 5. GET /v1/usage

토큰·비용·요청 수 집계.

### Query Parameters

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| `from` | ISO8601 date | N | default: 7일 전 |
| `to` | ISO8601 date | N | default: 오늘 (`SIM_TODAY`) |
| `group_by` | string | N | `day` / `model` / `agent` |

### Response 200

```json
{
  "request_id": "...",
  "cached": false,
  "data": {
    "period": { "from": "2026-05-24", "to": "2026-05-31" },
    "summary": {
      "total_requests": 1240,
      "cache_hits": 412,
      "cache_hit_ratio": 0.332,
      "total_tokens": 890000,
      "estimated_cost_usd": 12.45
    },
    "breakdown": [
      {
        "date": "2026-05-31",
        "requests": 180,
        "tokens": 120000,
        "cost_usd": 1.82
      }
    ]
  }
}
```

인증된 API Key/JWT **본인** 데이터만 조회 (관리자 전체 조회는 **TODO**).

---

## 6. GET /v1/models

사용 가능 LLM 목록 (Gateway 허용 목록).

### Response 200

```json
{
  "request_id": "...",
  "cached": true,
  "data": {
    "models": [
      {
        "id": "gpt-4o-mini",
        "provider": "openai",
        "default_for": ["chat", "md"],
        "max_tokens": 128000
      },
      {
        "id": "claude-3-5-sonnet-20241022",
        "provider": "anthropic",
        "default_for": ["voc", "insight"],
        "max_tokens": 200000
      }
    ],
    "defaults": {
      "chat": "gpt-4o-mini",
      "sql": "gpt-4o-mini"
    }
  }
}
```

> **TODO (구현):** 환경 변수 `ENABLED_MODELS`와 동기화.

---

## 7. 엔드포인트 요약

| Method | Path | 인증 | Rate Limit | Cache |
|--------|------|------|------------|-------|
| POST | `/v1/chat` | Y | Y | Y |
| POST | `/v1/agent/run` | Y | Y | Y |
| POST | `/v1/sql/generate` | Y | Y | N |
| GET | `/v1/usage` | Y | Y | N |
| GET | `/v1/models` | Y | Y | Y (장 TTL) |
| GET | `/health` | N | N | N |
| GET | `/ready` | N | N | N |

---

## 8. 구현 메모 (FastAPI)

```text
app/
├── main.py
├── api/v1/chat.py
├── api/v1/agent.py
├── api/v1/sql.py
├── api/v1/usage.py
├── middleware/auth.py
├── middleware/rate_limit.py
└── services/cache.py
```

> **TODO (구현 후):** OpenAPI 3.1 YAML을 `docs/openapi.yaml`로 export하고 본 문서와 diff 검증.

---

## 9. 변경 이력

| 버전 | 날짜 | 변경 |
|------|------|------|
| 1.0 | 2026-05-31 | API 초안 |
