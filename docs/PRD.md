# PRD: AI Commerce Operations Platform

| 항목 | 내용 |
|------|------|
| 문서 버전 | 1.0 |
| 작성일 | 2026-05-31 |
| 상태 | Draft |
| 참조 문서 | [PROJECT.md](./PROJECT.md) |

---

## 1. 배경 및 문제 정의

### 1.1 배경

커머스 조직(MD, CS, 운영팀)은 판매량 분석, VOC 분석, 매출 리포트 등 데이터 기반 업무를 반복적으로 수행한다. 이러한 업무는 SQL 작성, 리뷰 수동 분류, 리포트 작성 등 반복 작업이 많아 시간과 인력이 소모된다.

### 1.2 문제

- **데이터 접근 장벽**: 비전문가가 PostgreSQL 등 분석 DB에 직접 쿼리하기 어렵다.
- **반복 업무**: 동일 유형의 분석·리포트 요청이 지속적으로 발생한다.
- **VOC 처리 지연**: 리뷰·고객 불만 분석이 수동으로 이루어져 인사이트 도출이 느리다.
- **AI 요청 분산**: LLM 호출이 개별 서비스에 흩어져 인증, 비용 추적, Rate Limit 관리가 어렵다.

### 1.3 제품 비전

Olist 커머스 데이터를 기반으로, **자연어 질의 → AI Agent → 데이터 분석 → 인사이트 제공** 흐름을 표준화하는 LLM Agent 기반 커머스 운영 자동화 플랫폼을 구축한다. 단순 챗봇이 아닌, Gateway·Multi Agent·이벤트·배치 파이프라인을 갖춘 **운영 가능한 AI 플랫폼**을 목표로 한다.

---

## 2. 목표 및 성공 지표

### 2.1 비즈니스 목표

| 팀 | 자동화 대상 업무 |
|----|------------------|
| MD | 판매량 분석, 카테고리 분석, 프로모션 추천 |
| CS | VOC 분석, 리뷰 분류, 고객 불만 분석 |
| 운영팀 | 매출 리포트, 재고 분석, KPI 모니터링 |

### 2.2 제품 목표

1. 자연어로 커머스 데이터를 조회·분석할 수 있는 Multi Agent 제공
2. 전사 AI 요청의 단일 진입점(AI API Gateway) 확보
3. 실시간(이벤트)과 배치(일별 집계) 처리 분리로 Agent 응답 품질·속도 확보
4. AWS 배포 및 부하 테스트로 운영 환경 검증

### 2.3 성공 지표 (KPI)

| 지표 | 목표 |
|------|------|
| 동시 사용자 | 500~1,000 |
| Cache Hit 시 P95 지연 | < 300ms |
| Agent 호출 P95 지연 | < 10s |
| 오류율 | < 1% |
| 캐시 적중률 | > 30% |

---

## 3. 사용자 및 페르소나

### 3.1 MD (Merchandising)

- **니즈**: 카테고리·상품별 매출, 재구매율, 프로모션 대상 파악
- **예시 질의**: "이번 달 판매량이 감소한 상품 알려줘", "카테고리별 매출 순위 알려줘"

### 3.2 CS (Customer Service)

- **니즈**: 부정 리뷰·VOC 트렌드, 품질·배송 관련 불만 파악
- **예시 질의**: "최근 부정 리뷰가 증가한 상품 알려줘", "배송 관련 VOC 알려줘"

### 3.3 운영팀 (Operations)

- **니즈**: 매출 KPI, 감소 원인, 고객 이탈 등 경영·운영 리포트
- **예시 질의**: "매출 감소 원인 분석해줘", "고객 이탈 분석해줘"

### 3.4 플랫폼/개발 (내부)

- **니즈**: API Key·JWT 인증, 사용량·비용 추적, Rate Limit, 모델 목록 조회

---

## 4. 핵심 사용자 시나리오

### 4.1 MD Agent — 판매량 감소 상품 조회

1. 사용자: "이번 달 판매량이 감소한 상품 알려줘"
2. Gateway: 인증·Rate Limit·캐시 확인
3. Agent Router → MD Agent
4. Text-to-SQL → PostgreSQL 조회 → LLM 분석 → 결과 반환

**기대 결과**: 감소 상품 목록과 요약 인사이트(자연어)

### 4.2 VOC Agent — 부정 리뷰 증가 상품

1. 사용자: "최근 부정 리뷰가 증가한 상품 알려줘"
2. 리뷰 검색 → 감성 분석 → VOC 분류 → 요약

**기대 결과**: 상품별 부정 리뷰 추이 및 주요 VOC 유형

### 4.3 Insight Agent — 매출 감소 원인 분석

1. 사용자: "매출 감소 원인 분석해줘"
2. KPI·집계 데이터 조회 → 다차원 분석 → 리포트 생성

**기대 결과**: 구조화된 원인 분석 및 권장 액션(자연어 리포트)

---

## 5. 기능 요구사항

### 5.1 AI API Gateway (Must Have)

| ID | 요구사항 | 상세 |
|----|----------|------|
| GW-01 | 인증 | API Key, JWT 지원 |
| GW-02 | Rate Limiting | 사용자/API Key 기준 100 req/min |
| GW-03 | 캐시 | Redis 기반 동일 질의 재사용 |
| GW-04 | 사용량 추적 | 토큰 사용량, 비용, 응답 시간 기록 |
| GW-05 | REST API | `POST /v1/chat`, `POST /v1/agent/run`, `POST /v1/sql/generate`, `GET /v1/usage`, `GET /v1/models` |

### 5.2 Multi Agent Runtime (Must Have)

| Agent | 기능 | 예시 질의 |
|-------|------|-----------|
| MD Agent | 매출·상품 분석, 프로모션 추천 | 카테고리별 매출, 재구매율, 프로모션 대상 |
| VOC Agent | 리뷰·감성·VOC 분류 | 품질/배송 불만, VOC 트렌드 |
| Insight Agent | KPI 분석, 리포트 생성 | 매출 감소 원인, 고객 이탈 |

| ID | 요구사항 | 상세 |
|----|----------|------|
| AG-01 | Agent Router | 질의 유형에 따른 Agent 라우팅 |
| AG-02 | Text-to-SQL | 자연어 → SQL 생성 및 PostgreSQL 실행 |
| AG-03 | Prompt Versioning | `prompt_versions` 테이블 기반 버전 관리 |
| AG-04 | 실행 로깅 | `agent_requests`, `agent_executions` 저장 |

### 5.3 데이터 레이어 (Must Have)

**원본 데이터 (Olist)**

- `customers`, `orders`, `order_items`, `products`, `reviews`, `payments`, `sellers`, `category_translation`

**운영·분석 테이블**

- `agent_requests`, `agent_executions`, `prompt_versions`, `model_usage_logs`, `review_analysis`, `daily_category_metrics`, `api_keys`

### 5.4 Kafka 이벤트 파이프라인 (Must Have)

| Topic | 용도 | Consumer |
|-------|------|----------|
| `review_created` | 신규 리뷰 | Review Analyzer (감성·VOC) |
| `review_analyzed` | 분석 완료 | Metric Aggregator 등 |
| `metric_updated` | 집계 완료 | Usage Logger (토큰 등) |

### 5.5 Airflow 배치 (Must Have)

**DAG: `daily_commerce_ops_pipeline`**

`extract_orders` → `extract_reviews` → `review_classification` → `aggregate_sales_metrics` → `aggregate_voc_metrics` → `quality_check` → `load_daily_metrics`

**목적**: 일별 KPI, VOC 통계, Agent 조회용 사전 집계 데이터 생성

### 5.6 Redis (Must Have)

- 질의 결과 캐시
- 대화 세션(이력) 관리
- Rate Limit 카운터

---

## 6. 비기능 요구사항

| 영역 | 요구사항 |
|------|----------|
| 성능 | 동시 500~1,000 사용자, Agent P95 < 10s, Cache P95 < 300ms |
| 가용성 | 오류율 < 1% (k6 부하 테스트 기준) |
| 확장성 | Kafka Consumer, Agent Worker 수평 확장 가능 구조 |
| 보안 | API Key/JWT, 사용량·비용 감사 로그 |
| 관측성 | `model_usage_logs`, Gateway 사용량 API |
| 배포 | Docker Compose, AWS EC2 |

---

## 7. 기술 스택 (제약)

| 영역 | 기술 |
|------|------|
| Backend | FastAPI (Python) |
| DB | PostgreSQL |
| Cache | Redis |
| Event | Kafka |
| Workflow | Airflow |
| LLM | OpenAI / Claude |
| Agent Framework | LangGraph |
| Infra | Docker Compose, AWS EC2 |
| Load Test | k6 |

---

## 8. 범위

### 8.1 In Scope (v1)

- Olist 데이터 적재 및 ERD/DDL
- AI API Gateway (인증, 캐시, Rate Limit, Usage)
- MD / VOC / Insight Agent 및 Text-to-SQL
- Kafka Producer/Consumer (Review Analyzer, Metric Aggregator, Usage Logger)
- Airflow 일별 DAG
- Docker Compose + AWS EC2 배포
- k6 부하 테스트 (4 시나리오)

### 8.2 Out of Scope (v1)

- 실제 Olist 외 운영 DB 연동
- 프론트엔드 UI (API·Agent 중심)
- 멀티 테넌트 SaaS 과금
- 실시간 재고·물류 외부 시스템 연동

---

## 9. API 개요

| Method | Path | 설명 |
|--------|------|------|
| POST | `/v1/chat` | 일반 채팅/질의 |
| POST | `/v1/agent/run` | 특정 Agent 실행 |
| POST | `/v1/sql/generate` | Text-to-SQL |
| GET | `/v1/usage` | 사용량·비용 조회 |
| GET | `/v1/models` | 사용 가능 모델 목록 |

---

## 10. 마일스톤 (5일 개발 일정)

| 일차 | 목표 | 주요 산출물 |
|------|------|-------------|
| Day 1 | DB 구축 | ERD, DDL, Seed Script, Olist 적재 |
| Day 2 | AI Gateway | FastAPI, JWT/API Key, Redis, Rate Limit, Usage Logging |
| Day 3 | Agent | MD/VOC Agent, Text-to-SQL, Prompt Versioning |
| Day 4 | Kafka | Producer/Consumer, Review Analysis Table |
| Day 5 | Airflow·배포·검증 | DAG, Docker Compose, AWS, k6 리포트, README |

---

## 11. 최종 산출물

- GitHub Repository
- Architecture Diagram
- ERD
- API Specification
- Kafka Pipeline 문서
- Airflow DAG
- Docker Compose
- k6 Load Test Report
- README
- Demo Video

---

## 12. 리스크 및 가정

| 구분 | 내용 |
|------|------|
| 가정 | Olist 데이터셋으로 커merce 시나리오 대표 가능 |
| 가정 | OpenAI/Claude API 키 및 네트워크 접근 가능 |
| 리스크 | LLM SQL 생성 오류 → 품질 검증·프롬프트 버전 관리 필요 |
| 리스크 | Agent P95 10s 목표 → 캐시·사전 집계(Airflow) 의존 |
| 리스크 | Kafka/Airflow 운영 복잡도 → Docker Compose로 v1 단순화 |

---

## 13. 부하 테스트 시나리오 (k6)

1. 단순 조회
2. MD Agent 호출
3. VOC Agent 호출
4. 리뷰 이벤트 대량 발행

---

## 14. 승인 및 변경 이력

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|-----------|--------|
| 1.0 | 2026-05-31 | PROJECT.md 기반 초안 | — |