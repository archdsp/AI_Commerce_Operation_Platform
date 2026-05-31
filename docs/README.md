> **상태:** Draft (Pre-implementation)

# 문서 인덱스

AI Commerce Operations Platform 사전 개발 문서 모음. 구현 전 설계·명세 참조용.

---

## 요구사항·개요

| 문서 | 한 줄 설명 |
|------|-----------|
| [PRD.md](./PRD.md) | 제품 요구사항, KPI, 범위, 마일스톤 |
| [PROJECT.md](./PROJECT.md) | 프로젝트 개요, 시나리오, 기술 스택 요약 |

---

## 설계·명세 (Pre-implementation)

| 문서 | 한 줄 설명 |
|------|-----------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Gateway·Agent·DB·Kafka·Workers·Airflow 컴포넌트 및 동기/비동기 흐름 |
| [ERD.md](./ERD.md) | Olist + 운영 테이블 논리 ERD, 인덱스, FK (`db/schema/` 예정) |
| [DATA.md](./DATA.md) | Olist 출처, seed 순서, DB 분리, SIM_TODAY·sim_* 시뮬레이션 |
| [API.md](./API.md) | REST API 전체 명세, 인증·캐시·Rate Limit·에러 코드 |
| [AGENTS.md](./AGENTS.md) | MD/VOC/Insight Agent, 라우팅, Text-to-SQL 가드레일, 예시 질의 20건 |
| [KAFKA.md](./KAFKA.md) | 토픽 3종, JSON 스키마, Producer/Consumer, replay |
| [AIRFLOW.md](./AIRFLOW.md) | `daily_commerce_ops_pipeline` DAG 태스크·품질 규칙 |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Docker Compose, `.env`, 기동 순서, EC2 계획 |
| [LOAD_TEST.md](./LOAD_TEST.md) | k6 시나리오 1~4, KPI, 결과 TODO |
| [DEMO_SCRIPT.md](./DEMO_SCRIPT.md) | 5~10분 MD/CS/운영 데모 스크립트 |

---

## 읽는 순서 (권장)

1. PRD → PROJECT  
2. ARCHITECTURE → ERD → DATA  
3. API + AGENTS  
4. KAFKA + AIRFLOW  
5. DEPLOYMENT → LOAD_TEST → DEMO_SCRIPT  

---

## 구현 후 갱신 TODO

- [ ] `docs/openapi.yaml` export ([API.md](./API.md))
- [ ] `db/schema/` DDL과 [ERD.md](./ERD.md) 동기화
- [ ] [LOAD_TEST.md](./LOAD_TEST.md) §9 실측 결과
- [ ] [DEPLOYMENT.md](./DEPLOYMENT.md) §7 트러블슈팅
- [ ] 문서 상태를 `Implemented`로 변경
