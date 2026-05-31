# TODO — 남은 구현 갭

> `docs/` 명세(PRD §5) 대비 미구현/부분 항목. 완성도 매트릭스·스택 매핑: [PROGRESS.md §8·§9](./PROGRESS.md).
> 우선순위: **P1** 데모·정확도 직접 영향 · **P2** 운영·관측성 · **P3** 문서 명세이나 재정렬로 대체/보류.

## P1 — 데모·품질 직접 영향
- [ ] **사용량 토큰·비용 추적 (GW-04)** — `model_usage_logs.prompt_tokens/completion_tokens/estimated_cost_usd` 미기록.
  `common/llm.py`가 vLLM `usage`를 반환 → `gateway/app.py:_log`에서 기록 → `/v1/usage` 집계 노출. provider 단가표 필요.
- [ ] **Agent Router LLM fallback (AG-01)** — `agents/graph.py:route` 가 키워드 미스 시 'md' 기본. 모호 질의용 LLM 1회 분류 추가.
- [ ] **Text-to-SQL 회귀 테스트** — `AGENTS.md §6`의 20개 질의로 스키마/필드 존재 검증 (`tests/agents/test_regression_queries.py`). LLM 비결정성 고려해 결과값이 아닌 구조 검증.

## P2 — 운영·관측성
- [ ] **Usage Logger 컨슈머** — `metric_updated`(및 Gateway 직접 기록) 소비해 토큰/비용 보강 (ARCHITECTURE §5.4, PRD 5.4).
- [ ] **Prompt Versioning 활성화 (AG-03)** — `prompt_versions` 테이블을 코드가 로드하도록(현재 `agents/prompts.py` 하드코딩). 응답 `metadata.prompt_version` 노출.
- [ ] **k6 부하 테스트 4시나리오** — `LOAD_TEST.md`: 단순조회 / MD / VOC / 리뷰 대량발행. 목표 P95·오류율·캐시적중 측정.
- [ ] **게이트웨이 통합 테스트** — 인증 401/200, `/v1/*` 스모크 (pytest + FastAPI TestClient).
- [ ] **Airflow DAG 완성·배포** — 현재 2태스크 → 필요 시 문서 7태스크(staging 분리)로 확장. **MWAA S3 실배포** 확인 (`mwaa/finish_mwaa_setup.py`).

## P3 — 문서 명세이나 재정렬로 대체/보류
- [ ] **JWT 인증 (GW-01)** — 현재 API Key만. 필요 시 `Authorization: Bearer` HS256 추가.
- [ ] **Redis 캐시·세션 (GW-03 / 5.6)** — 질의 해시 캐시 + 대화 세션. (Rate Limit은 API Gateway Usage Plan으로 대체 완료)
- [ ] **Docker Compose** — 현재 실 AWS 관리형 사용. 로컬 재현용으로만 선택.
- [ ] **Demo Video** — 최종 산출물.

## 정리(하우스키핑)
- [ ] `scripts/run_gateway.py` 커밋 여부 결정 (현재 untracked).
- [ ] `.env.example` 로컬 PG 스캐폴딩 섹션 정합성 점검.
- [ ] API Gateway IaC: ACM 커스텀 도메인 / WAF / CloudWatch 액세스 로그 추가.

---
갱신: 2026-05-31 · 기준 문서: `docs/` + `PROGRESS.md`
