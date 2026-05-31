> **상태:** 구현 반영(REALIGNED) — 실제 스택: RDS MySQL · MSK(IAM) · MWAA · RunPod vLLM(Qwen2.5-7B) · Qdrant · AWS API Gateway. 본 문서의 PostgreSQL/Redis/Docker Compose/OpenAI·Claude 언급은 구현과 다름 — 스택 매핑·완성도는 [PROGRESS.md](../PROGRESS.md) 참조. (k6 자체는 아직 미구현)

# k6 부하 테스트 계획

| 항목 | 내용 |
|------|------|
| 문서 버전 | 1.0 |
| 작성일 | 2026-05-31 |
| 도구 | [k6](https://k6.io/) |

---

## 1. 목표 KPI (PRD / PROJECT §13)

| 지표 | 목표 | 측정 방법 |
|------|------|-----------|
| 동시 사용자 (VU) | 500 ~ 1,000 | k6 `vus` / `stages` |
| Cache Hit P95 지연 | **< 300ms** | `cached=true` 응답만 |
| Agent 호출 P95 | **< 10s** | `cached=false`, chat/agent |
| 오류율 | **< 1%** | HTTP non-2xx + 타임아웃 |
| 캐시 적중률 | **> 30%** | Gateway 로그 또는 `/v1/usage` |

> **TODO (테스트 실행 후):** §6 결과 섹션에 실측값·그래프 기록.

---

## 2. 테스트 환경

| 항목 | 값 |
|------|-----|
| 대상 URL | `http://<host>:8000` |
| 인증 | `X-API-Key` (시드 키) |
| `SIM_TODAY` | 고정 `2026-05-31` |
| 사전 조건 | Olist seed 완료, Agent·Kafka·Redis 기동, 캐시 워밍 선택 |

부하 생성기: k6를 Gateway와 **분리** (동일 EC2 가능, CPU 경합 주의).

---

## 3. 시나리오 1 — 단순 조회

**목적:** Gateway 오버헤드·캐시·Rate Limit 기준선.

| 파라미터 | 값 |
|----------|-----|
| 엔드포인트 | `GET /v1/models`, `GET /v1/usage` |
| VU | 200 → 500 (5분 ramp) |
| Duration | 10분 |
| RPS 목표 | ~50 (엔드포인트 합산) |

**성공 기준:** P95 < 200ms, error < 0.5%

```javascript
// tests/k6/scenario1_simple.js — TODO: 구현
import http from 'k6/http';
export const options = { stages: [{ duration: '5m', target: 500 }] };
export default function () {
  http.get(`${__ENV.BASE_URL}/v1/models`, { headers: { 'X-API-Key': __ENV.API_KEY } });
}
```

---

## 4. 시나리오 2 — MD Agent 호출

**목적:** Text-to-SQL + LLM 경로 P95 < 10s.

| 파라미터 | 값 |
|----------|-----|
| 엔드포인트 | `POST /v1/agent/run` (`agent_type=md`) |
| VU | 50 → 200 |
| Duration | 15분 |
| 질의 풀 | [AGENTS.md §6](./AGENTS.md) MD 1~7번 순환 |

**캐시:** 1차 전체 cold → 2차 동일 질의 30% 혼합 (hit ratio 검증).

**성공 기준:** uncached P95 < 10s, error < 1%

---

## 5. 시나리오 3 — VOC Agent 호출

| 파라미터 | 값 |
|----------|-----|
| 엔드포인트 | `POST /v1/chat` (auto → voc) 또는 `agent_type=voc` |
| VU | 50 → 200 |
| Duration | 15분 |
| 질의 풀 | AGENTS VOC 8~13번 |

**성공 기준:** 시나리오 2와 동일.

---

## 6. 시나리오 4 — 리뷰 이벤트 대량 발행

**목적:** Kafka + Review Analyzer 처리량 (HTTP와 병행).

| 파라미터 | 값 |
|----------|-----|
| 도구 | `scripts/kafka_replay_reviews.py` + k6 HTTP 혼합 |
| 이벤트 수 | 10,000 ~ 50,000 |
| 발행 속도 | 500 events/sec (조정 가능) |
| 병행 HTTP | `POST /v1/chat` VOC 20 VU |

**성공 기준:**

- Consumer lag → 0 (30분 이내)
- `review_analysis` 건수 일치 (±1%)
- HTTP error < 1% 유지

상세: [KAFKA.md §Replay](./KAFKA.md)

---

## 7. 혼합 시나리오 (선택)

| 비율 | 트래픽 |
|------|--------|
| 40% | 시나리오 1 |
| 30% | 시나리오 2 |
| 20% | 시나리오 3 |
| 10% | 시나리오 4 (이벤트 only) |

VU 합계 1,000 — **TODO:** CPU/LLM quota 한도 확인 후 실행.

---

## 8. 메트릭 수집

| 소스 | 메트릭 |
|------|--------|
| k6 | `http_req_duration`, `http_req_failed`, `vus` |
| Gateway | `cache_hit`, `latency_ms` (logs) |
| Redis | `INFO stats` keyspace hits |
| Postgres | slow query log **TODO** |
| Kafka | consumer lag |

k6 출력:

```bash
k6 run --out json=results/scenario2.json tests/k6/scenario2_md.js
```

---

## 9. 결과 (Post-Test) — TODO

> **구현·테스트 완료 후 아래 표를 채운다.**

| 시나리오 | VU max | P50 | P95 | P99 | Error % | Cache Hit % | Pass |
|----------|--------|-----|-----|-----|---------|-------------|------|
| 1 단순 | — | — | — | — | — | — | — |
| 2 MD | — | — | — | — | — | — | — |
| 3 VOC | — | — | — | — | — | — | — |
| 4 Kafka | — | lag — | — | — | — | N/A | — |

### 9.1 병목 분석 TODO

- [ ] LLM rate limit
- [ ] Postgres connection pool
- [ ] Kafka partition 수
- [ ] Redis memory

### 9.2 개선 액션 TODO

- [ ] 캐시 TTL 조정
- [ ] `daily_category_metrics` 사전 집계 확대
- [ ] Agent worker replica

---

## 10. 실행 체크리스트 (Day 5)

- [ ] `.env` 프로덕션 유사 설정
- [ ] `SIM_TODAY` 고정 문서화
- [ ] API Key 시드
- [ ] 시나리오 1→4 순차 실행
- [ ] 결과 JSON → `docs/reports/load_test_YYYYMMDD.md` **TODO**

---

## 11. 변경 이력

| 버전 | 날짜 | 변경 |
|------|------|------|
| 1.0 | 2026-05-31 | 부하 테스트 계획 초안 |
