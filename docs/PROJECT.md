# AI Commerce Operations Platform

> LLM Agent 기반 커머스 운영 자동화 플랫폼

> **⚠️ 스택 현행화(REALIGNED):** 실제 구현은 RDS MySQL · MSK(IAM) · MWAA · RunPod vLLM(Qwen2.5-7B) · Qdrant · AWS API Gateway. 아래 PostgreSQL/Redis/Docker Compose/OpenAI·Claude 언급은 [PROGRESS.md §9 스택 매핑](../PROGRESS.md)으로 대체됨.

---

# 1. 프로젝트 개요

Olist 커머스 데이터를 기반으로 MD, CS, 운영팀이 반복적으로 수행하는 데이터 조회, 리뷰 분석, 매출 분석, 상품 운영 업무를 AI Agent로 자동화한다.

본 프로젝트는 단순 챗봇이 아닌 다음 영역을 포함하는 AI 플랫폼 구축을 목표로 한다.

- AI API Gateway
- Multi Agent Runtime
- Kafka Event Pipeline
- Airflow Batch Pipeline
- Redis Cache
- PostgreSQL Analytics
- LLM 기반 업무 자동화

---

# 2. 프로젝트 목표

## 비즈니스 목표

커머스 조직의 반복 업무 자동화

### MD

- 판매량 분석
- 카테고리 분석
- 프로모션 추천

### CS

- VOC 분석
- 리뷰 분류
- 고객 불만 분석

### 운영팀

- 매출 리포트
- 재고 분석
- KPI 모니터링

---

## 기술 목표

- AI API Gateway 구축
- LLM Agent 운영 플랫폼 구축
- Kafka 기반 이벤트 처리
- Airflow 기반 배치 파이프라인 구축
- Redis 기반 캐싱 및 Rate Limiting
- AWS 배포
- k6 기반 부하 테스트

---

# 3. 사용 데이터

## Dataset

Olist Brazilian E-Commerce Dataset

### 사용 테이블

```text
customers
orders
order_items
products
reviews
payments
sellers
category_translation
```

### 주요 분석 대상

```text
고객
주문
상품
카테고리
결제
리뷰
판매자
배송
```

---

# 4. 핵심 시나리오

## MD Agent

사용자 질문

```text
이번 달 판매량이 감소한 상품 알려줘
```

처리

```text
질문 수신
→ SQL 생성
→ PostgreSQL 조회
→ LLM 분석
→ 결과 생성
```

---

## VOC Agent

사용자 질문

```text
최근 부정 리뷰가 증가한 상품 알려줘
```

처리

```text
리뷰 검색
→ 감성 분석
→ VOC 분류
→ 요약
```

---

## Insight Agent

사용자 질문

```text
매출 감소 원인 분석해줘
```

처리

```text
데이터 조회
→ KPI 분석
→ 리포트 생성
```

---

# 5. 시스템 아키텍처

```text
User

│

▼

AI API Gateway

│

├── Authentication
├── Rate Limit
├── Cache
├── Usage Logging

│

▼

Agent Router

│

├── MD Agent
├── VOC Agent
└── Insight Agent

│

▼

PostgreSQL

│

▼

Kafka

│

├── review_created
├── review_analyzed
└── metric_updated

│

▼

Workers

│

├── Review Analyzer
├── Embedding Worker
└── Metric Aggregator

│

▼

Airflow

│

├── Daily ETL
├── Aggregation
├── Quality Check
└── Reporting
```

---

# 6. 기술 스택

| 영역 | 기술 (실제 구현) |
|--------|--------|
| Backend | FastAPI |
| Language | Python |
| Database | **RDS MySQL 8.4** _(문서 원안: PostgreSQL)_ |
| Cache / Rate Limit | **AWS API Gateway Usage Plan** _(Redis 미도입)_ |
| Event Streaming | **AWS MSK Serverless (IAM)** |
| Workflow | **AWS MWAA** (Airflow) |
| LLM | **RunPod vLLM — Qwen2.5-7B-Instruct** _(문서 원안: OpenAI/Claude)_ |
| Vector DB / RAG | **Qdrant + fastembed** _(문서 외 추가)_ |
| Agent | LangGraph |
| API 관문 | **AWS API Gateway (REST)** + Terraform IaC |
| Cloud | AWS (EC2 시뮬·게이트웨이 + 관리형) |
| Load Test | k6 _(미구현)_ |

---

# 7. AI API Gateway

## 역할

전사 AI 요청 단일 진입점

---

## 기능

### 인증

```text
API Key
JWT
```

---

### 캐시

```text
Redis Cache
```

---

### Rate Limiting

```text
100 req/min
```

---

### 사용량 추적

```text
토큰 사용량
비용
응답 시간
```

---

## API

```http
POST /v1/chat

POST /v1/agent/run

POST /v1/sql/generate

GET /v1/usage

GET /v1/models
```

---

# 8. Agent 설계

## MD Agent

### 기능

- 매출 분석
- 상품 분석
- 프로모션 추천

### 예시

```text
카테고리별 매출 순위 알려줘

재구매율 높은 상품 알려줘

프로모션 대상 추천해줘
```

---

## VOC Agent

### 기능

- 리뷰 분석
- 감성 분석
- VOC 분류

### 예시

```text
최근 품질 관련 불만 알려줘

배송 관련 VOC 알려줘
```

---

## Insight Agent

### 기능

- KPI 분석
- 리포트 생성

### 예시

```text
매출 감소 원인 알려줘

고객 이탈 분석해줘
```

---

# 9. 데이터베이스 설계

## Olist 원본

```sql
customers
orders
order_items
products
reviews
payments
sellers
```

---

## 운영 테이블

```sql
agent_requests

agent_executions

prompt_versions

model_usage_logs

review_analysis

daily_category_metrics

api_keys
```

---

# 10. Kafka 설계

## Topic

### review_created

신규 리뷰 이벤트

---

### review_analyzed

리뷰 분석 완료 이벤트

---

### metric_updated

집계 완료 이벤트

---

## Consumer

### Review Analyzer

```text
감성 분석
VOC 분류
```

---

### Metric Aggregator

```text
매출 집계
카테고리 집계
```

---

### Usage Logger

```text
토큰 사용량 저장
```

---

# 11. Airflow 설계

## DAG

### daily_commerce_ops_pipeline

```text
extract_orders

↓

extract_reviews

↓

review_classification

↓

aggregate_sales_metrics

↓

aggregate_voc_metrics

↓

quality_check

↓

load_daily_metrics
```

---

## 목적

- 일별 KPI 생성
- VOC 통계 생성
- 리뷰 분석 자동화
- Agent 조회용 데이터 생성

---

# 12. Redis 활용

## Cache

동일 질문 재사용

```text
질문

↓

Redis Hit

↓

즉시 응답
```

---

## Session

```text
대화 이력 관리
```

---

## Rate Limit

```text
사용자별 요청 제한
```

---

# 13. 성능 검증

## k6 부하 테스트

### Scenario 1

```text
단순 조회
```

---

### Scenario 2

```text
MD Agent 호출
```

---

### Scenario 3

```text
VOC Agent 호출
```

---

### Scenario 4

```text
리뷰 이벤트 대량 발행
```

---

## 목표

| 항목 | 목표 |
|--------|--------|
| Concurrent Users | 500~1000 |
| Cache Latency P95 | < 300ms |
| Agent Latency P95 | < 10s |
| Error Rate | < 1% |
| Cache Hit Ratio | > 30% |

---

# 14. 개발 일정

## Day 1

### 데이터베이스 구축

- Olist 적재
- PostgreSQL 구성
- ERD 작성

### 산출물

```text
ERD
DDL
Seed Script
```

---

## Day 2

### AI Gateway 구축

- FastAPI
- JWT
- API Key
- Redis Cache
- Rate Limit

### 산출물

```text
Gateway API
Redis Module
Usage Logging
```

---

## Day 3

### Agent 구현

- MD Agent
- VOC Agent
- Text-to-SQL

### 산출물

```text
Agent Runtime
Prompt Template
Prompt Versioning
```

---

## Day 4

### Kafka 구현

- Producer
- Consumer
- Review Analyzer

### 산출물

```text
Kafka Pipeline
Review Analysis Table
```

---

## Day 5

### Airflow 및 배포

- DAG 작성
- Docker Compose
- AWS 배포
- k6 테스트

### 산출물

```text
Airflow DAG
Deployment Guide
Load Test Report
README
```

---

# 15. 최종 산출물

- GitHub Repository
- Architecture Diagram
- ERD
- API Specification
- Kafka Pipeline
- Airflow DAG
- Docker Compose
- k6 Load Test Report
- README
- Demo Video

---

# 16. 요약

AI Commerce Operations Platform을 설계 및 구현하여 커머스 조직의 반복 업무를 LLM Agent 기반으로 자동화했습니다. FastAPI 기반 AI API Gateway를 구축하여 인증, 사용량 추적, Redis Cache, Rate Limiting을 중앙화했고, MD Agent와 VOC Agent를 통해 자연어 기반 매출 분석 및 리뷰 분석 기능을 제공했습니다. Kafka 기반 이벤트 처리 파이프라인과 Airflow 기반 배치 워크플로우를 구성하여 실시간 처리와 일별 데이터 집계를 분리했으며, AWS 환경 배포 및 k6 부하 테스트를 통해 운영 환경을 검증했습니다.