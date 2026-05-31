# AI Commerce Operations Platform

> Olist 커머스 데이터 기반 LLM Agent 운영 자동화 플랫폼

| 항목 | 내용 |
|------|------|
| **현재 단계** | **Pre-implementation** — 설계·문서 완료 후 코드 구현 예정 |
| 문서 | [docs/README.md](./docs/README.md) |

---

## 소개

MD·CS·운영팀의 반복 데이터 업무(매출 분석, VOC, KPI 리포트)를 **자연어 → AI Agent → PostgreSQL → 인사이트** 흐름으로 자동화합니다.

단순 챗봇이 아니라 다음을 포함하는 운영 가능한 AI 플랫폼을 목표로 합니다.

- **AI API Gateway** — 인증(API Key/JWT), Rate Limit(100/min), Redis 캐시, 사용량 추적
- **Multi Agent** — MD / VOC / Insight + Text-to-SQL
- **Kafka** — 리뷰 생성·분석·집계 이벤트
- **Airflow** — 일별 KPI·`daily_category_metrics` 사전 집계
- **PostgreSQL** — Olist 원본(`olist_raw`) + 운영 DB(`commerce_ops`)

데이터셋: [Olist Brazilian E-Commerce](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (데모·PoC)

---

## 빠른 개요

```text
Client → Gateway → Agent Router → MD | VOC | Insight → PostgreSQL
                              ↘ Kafka → Workers → review_analysis
Airflow (daily) → daily_category_metrics → Agent 조회 가속
```

| API (주요) | 설명 |
|------------|------|
| `POST /v1/chat` | 자동 Agent 라우팅 질의 |
| `POST /v1/agent/run` | 지정 Agent 실행 |
| `POST /v1/sql/generate` | Text-to-SQL |
| `GET /v1/usage` | 토큰·비용·캐시 통계 |
| `GET /v1/models` | 허용 LLM 목록 |

성능 목표: 동시 500~1,000 사용자, Cache P95 &lt; 300ms, Agent P95 &lt; 10s, 오류율 &lt; 1%, 캐시 hit &gt; 30%.

---

## 문서 (docs/)

전체 인덱스: **[docs/README.md](./docs/README.md)**

| 문서 | 내용 |
|------|------|
| [PRD](./docs/PRD.md) | 제품 요구사항 |
| [PROJECT](./docs/PROJECT.md) | 프로젝트 상세 |
| [ARCHITECTURE](./docs/ARCHITECTURE.md) | 시스템 아키텍처 |
| [ERD](./docs/ERD.md) | 데이터 모델 |
| [DATA](./docs/DATA.md) | Olist·시뮬레이션·Seed |
| [API](./docs/API.md) | REST API 명세 |
| [AGENTS](./docs/AGENTS.md) | Agent·프롬프트·가드레일 |
| [KAFKA](./docs/KAFKA.md) | 이벤트 파이프라인 |
| [AIRFLOW](./docs/AIRFLOW.md) | 배치 DAG |
| [DEPLOYMENT](./docs/DEPLOYMENT.md) | Docker·EC2 배포 |
| [LOAD_TEST](./docs/LOAD_TEST.md) | k6 부하 테스트 |
| [DEMO_SCRIPT](./docs/DEMO_SCRIPT.md) | 데모 시나리오 |

---

## 기술 스택

FastAPI · PostgreSQL · Redis · Kafka · Airflow · LangGraph · OpenAI/Claude · Docker Compose · AWS EC2 · k6

---

## 5일 개발 일정 (예정)

| 일차 | 목표 |
|------|------|
| Day 1 | DB·ERD·Seed |
| Day 2 | AI Gateway |
| Day 3 | Agents·Text-to-SQL |
| Day 4 | Kafka·Workers |
| Day 5 | Airflow·Compose·k6·데모 |

---

## 로컬 실행

> **아직 구현 전입니다.** `docker-compose.yml` 및 애플리케이션 코드 추가 후 [DEPLOYMENT.md](./docs/DEPLOYMENT.md)를 따릅니다.

```bash
# 구현 후 예시
cp .env.example .env
docker compose up -d
```

---

## 라이선스·데이터

Olist 데이터셋 이용 시 Kaggle 라이선스를 준수합니다. 상세는 [DATA.md](./docs/DATA.md).

---

## 변경 상태

- **Pre-implementation:** 본 README 및 `docs/*` 설계 문서는 Draft 상태이며, 코드·DDL·Compose는 후속 일정에서 추가됩니다.
