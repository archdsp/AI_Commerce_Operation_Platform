> **상태:** 구현 반영(REALIGNED) — 실제 스택: RDS MySQL · MSK(IAM) · MWAA · RunPod vLLM(Qwen2.5-7B) · Qdrant · AWS API Gateway. 본 문서의 PostgreSQL/Redis/Docker Compose/OpenAI·Claude 언급은 구현과 다름 — 스택 매핑·완성도는 [PROGRESS.md](../PROGRESS.md) 참조. (k6 자체는 아직 미구현)

# k6 부하 테스트 계획 (미구현 · 계획)

| 항목 | 내용 |
|------|------|
| 문서 버전 | 2.0 |
| 작성일 | 2026-05-31 |
| 도구 | [k6](https://k6.io/) |
| 구현 상태 | **미구현(계획)** — `tests/k6/` 스크립트 없음. 우선순위 P2 ([../TODO.md](../TODO.md)) |

> **중요 (현실):** k6 시나리오는 **아직 작성되지 않았다**. 본 문서의 4시나리오·KPI·예시 스크립트는 모두 **계획(미실행)** 이다.
> 아래 §1 목표 KPI는 **희망치(aspirational)** 이며 **달성/검증되지 않았다**:
> - **Agent P95 < 10s**: 현재 `POST /v1/chat` 실측 지연은 **약 7~16s** (RunPod vLLM Qwen2.5-7B + Text-to-SQL 경로). 상한이 목표(10s)를 초과 → **목표 미달**.
> - **Cache Hit P95 < 300ms / 캐시 적중률 > 30%**: **캐시 계층이 존재하지 않음**. Gateway 응답에 `cached` 필드 없음 → 측정 불가/검증 불가.
> 진행 상황·근거는 [../PROGRESS.md](../PROGRESS.md), 작업 항목은 [../TODO.md](../TODO.md)(k6 = P2) 참조.

---

## 1. 목표 KPI (희망치 — 미검증)

| 지표 | 목표(희망) | 측정 방법(계획) | 현 상태 |
|------|-----------|----------------|---------|
| 동시 사용자 (VU) | 500 ~ 1,000 | k6 `vus` / `stages` | 미실행 |
| Agent 호출 P95 | **< 10s** | chat/agent 응답 `latency_ms` | **미달** — 실측 ~7~16s |
| Cache Hit P95 지연 | **< 300ms** | — | **N/A** — 캐시 없음 |
| 캐시 적중률 | **> 30%** | — | **N/A** — 캐시 없음 |
| 오류율 | **< 1%** | HTTP non-2xx + 타임아웃 | 미측정 |

> 위 목표는 PRD/PROJECT 초안에서 가져온 **설계 목표**이며, 구현·실행 후에야 검증 가능하다.

---

## 2. 테스트 환경 (계획)

| 항목 | 값 |
|------|-----|
| 대상 | **AWS API Gateway(REST) 엔드포인트** → FastAPI Gateway(`src/gateway/app.py`) |
| 인증 | API Gateway **API Key** (+ Usage Plan throttle). Gateway가 `X-Origin-Secret` 주입 → FastAPI 검증 |
| 백엔드 직접 호출(개발) | `http://<host>:8000`, 헤더 `X-API-Key: <시드 키>` (sha256 → `commerce_ops.api_keys`) |
| `SIM_TODAY` | 고정 `2026-05-31` |
| 사전 조건 | Olist seed 완료, RDS MySQL·MSK·RunPod vLLM·Qdrant 기동 |

> 실제 부하는 **AWS API Gateway**를 경유하므로, 게이트웨이 Usage Plan throttle(예: req/s, burst)이 1차 한계로 작용한다. FastAPI 백엔드 직접 부하는 throttle를 우회하므로 결과 해석에 주의.
> 부하 생성기: k6를 Gateway와 **분리** (동일 EC2 가능, CPU 경합 주의).

---

## 3. 시나리오 1 — 단순 조회 (계획)

**목적:** API Gateway throttle · Gateway 오버헤드 기준선.

| 파라미터 | 값 |
|----------|-----|
| 엔드포인트 | `GET /v1/models`, `GET /v1/usage` |
| VU | 200 → 500 (5분 ramp) |
| Duration | 10분 |
| RPS 목표 | ~50 (엔드포인트 합산) |

**성공 기준(희망):** P95 < 200ms, error < 0.5%

```javascript
// tests/k6/scenario1_simple.js — 미구현(계획)
import http from 'k6/http';
export const options = { stages: [{ duration: '5m', target: 500 }] };
export default function () {
  http.get(`${__ENV.BASE_URL}/v1/models`, {
    headers: { 'X-API-Key': __ENV.API_KEY },
  });
}
```

---

## 4. 시나리오 2 — MD Agent 호출 (계획)

**목적:** Text-to-SQL + RunPod vLLM(Qwen2.5-7B) 경로 P95 측정.

| 파라미터 | 값 |
|----------|-----|
| 엔드포인트 | `POST /v1/agent/run` (`agent_type=md`) |
| VU | 50 → 200 |
| Duration | 15분 |
| 질의 풀 | [AGENTS.md](./AGENTS.md) MD 질의 순환 (예: "카테고리별 매출 상위") |

**성공 기준(희망):** P95 < 10s, error < 1%
**현실:** 단건 실측 ~7~16s. **캐시가 없으므로** 동일 질의 반복도 cold 경로로 처리됨 — "hit ratio" 검증 불가.

```javascript
// tests/k6/scenario2_md.js — 미구현(계획)
import http from 'k6/http';
export const options = { stages: [{ duration: '15m', target: 200 }] };
export default function () {
  http.post(
    `${__ENV.BASE_URL}/v1/agent/run`,
    JSON.stringify({ agent_type: 'md', query: '카테고리별 매출 상위 알려줘' }),
    { headers: { 'X-API-Key': __ENV.API_KEY, 'Content-Type': 'application/json' } },
  );
}
```

---

## 5. 시나리오 3 — VOC Agent 호출 (계획)

| 파라미터 | 값 |
|----------|-----|
| 엔드포인트 | `POST /v1/chat` (auto → voc) 또는 `POST /v1/agent/run` (`agent_type=voc`) |
| VU | 50 → 200 |
| Duration | 15분 |
| 질의 풀 | VOC 질의 (예: "배송 관련 부정 리뷰 요약해줘") — Qdrant RAG 경로 포함 |

**성공 기준(희망):** 시나리오 2와 동일. **현실:** 동일하게 미검증, 캐시 없음.

---

## 6. 시나리오 4 — 리뷰 이벤트 대량 발행 (계획)

**목적:** AWS MSK + Review Analyzer 처리량 (HTTP와 병행).

| 파라미터 | 값 |
|----------|-----|
| 도구 | 리뷰 리플레이 스크립트(`scripts/`) + k6 HTTP 혼합 |
| 이벤트 수 | 10,000 ~ 50,000 |
| 발행 속도 | 500 events/sec (조정 가능) |
| 병행 HTTP | `POST /v1/chat` VOC 20 VU |

**성공 기준(희망):**

- MSK consumer lag → 0 (30분 이내)
- `review_analysis` 건수 일치 (±1%)
- HTTP error < 1% 유지

상세: [KAFKA.md](./KAFKA.md)

---

## 7. 혼합 시나리오 (선택 · 계획)

| 비율 | 트래픽 |
|------|--------|
| 40% | 시나리오 1 |
| 30% | 시나리오 2 |
| 20% | 시나리오 3 |
| 10% | 시나리오 4 (이벤트 only) |

VU 합계 1,000 — **계획:** AWS API Gateway throttle 한도 + RunPod vLLM 처리량 확인 후 실행.

---

## 8. 메트릭 수집 (계획)

| 소스 | 메트릭 | 상태 |
|------|--------|------|
| k6 | `http_req_duration`, `http_req_failed`, `vus` | 미구현 |
| Gateway | `latency_ms` (응답/`agent_requests` 테이블) | 가능 |
| `/v1/usage` | `total_requests`, `avg_latency_ms`, `by_endpoint`, `model_calls` | 가능 |
| AWS API Gateway | CloudWatch (Count, Latency, 4XX/5XX, throttle) | 가능 |
| AWS MSK | consumer lag (CloudWatch) | 가능 |

> 캐시 적중률·`cached` 메트릭은 **캐시 미구현**이라 수집 불가.

k6 출력(계획):

```bash
# tests/k6/scenario2_md.js 작성 후
k6 run --out json=results/scenario2.json tests/k6/scenario2_md.js
```

---

## 9. 결과 (Post-Test) — 미실행

> **k6 구현·실행 완료 후 아래 표를 채운다. 현재 모든 값 미측정.**

| 시나리오 | VU max | P50 | P95 | P99 | Error % | Pass |
|----------|--------|-----|-----|-----|---------|------|
| 1 단순 | — | — | — | — | — | — |
| 2 MD | — | — | — | — | — | — |
| 3 VOC | — | — | — | — | — | — |
| 4 MSK | — | lag — | — | — | — | — |

> 참고(단건, 부하 아님): `POST /v1/chat` 실측 지연 **~7~16s**. 캐시 컬럼 없음.

### 9.1 병목 분석 (예상 · 미검증)

- [ ] RunPod vLLM 처리량 / 토큰 생성 속도 (가장 유력 — P95 10s 초과 원인)
- [ ] AWS API Gateway Usage Plan throttle 한도
- [ ] RDS MySQL connection pool
- [ ] AWS MSK partition 수
- [ ] Qdrant 검색 지연 (VOC RAG)

### 9.2 개선 액션 (계획)

- [ ] **캐시 계층 도입** (미구현 — 현 응답에 `cached` 없음)
- [ ] `daily_category_metrics` 사전 집계 확대
- [ ] Agent/Gateway worker replica 확장
- [ ] RunPod 인스턴스/동시성 조정

---

## 10. 실행 체크리스트 (k6 구현 후)

- [ ] `tests/k6/` 시나리오 스크립트 1~4 작성 (**미구현**)
- [ ] `.env` 프로덕션 유사 설정 (RDS/MSK/RunPod/Qdrant 엔드포인트)
- [ ] `SIM_TODAY=2026-05-31` 고정 문서화
- [ ] API Gateway API Key + `commerce_ops.api_keys` 시드 키 준비
- [ ] 시나리오 1→4 순차 실행
- [ ] 결과 JSON → `docs/reports/load_test_YYYYMMDD.md`

---

## 11. 변경 이력

| 버전 | 날짜 | 변경 |
|------|------|------|
| 2.0 | 2026-05-31 | REALIGNED — 실제 스택/엔드포인트 반영 |
| 1.0 | 2026-05-31 | 부하 테스트 계획 초안 |
