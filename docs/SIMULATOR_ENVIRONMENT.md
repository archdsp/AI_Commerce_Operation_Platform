# Plan: AI Commerce Ops Platform — Olist 지역기반 실시간 스트리밍 + AWS관리형 + RunPod LLM

## Context
Olist 커머스 데이터를 **"마치 실시간처럼"** AWS MSK로 흘리고, RunPod 셀프호스팅 LLM + LangGraph 멀티에이전트로 *자연어 질의→분석→인사이트* 를 제공하는 AI Commerce Operations Platform을 5일/1인으로 구축한다. 되도록 AWS 관리형 사용.

**사용자 확정 결정**
- 엣지노드 단위 = **state/city (636개)** — 현실적 "지역 허브" 토폴로지
- 시뮬레이션 1차 목적 = **대용량·확장성 입증**

**핵심 통찰(실측):** 개별 셀러(3,095)는 2년간 중앙값 8건 → 엣지노드로 두면 대부분 침묵. 지역 묶음(state/city 636, 노드당 평균 177건)은 현실적이고 연속적. **총 이벤트는 그룹화와 무관하게 고정** → 부하 크기는 TAF(시간가속)·합성노드 복제로 조절. 목적이 scale-demo이므로 **636 베이스 + 합성복제 + 고TAF로 MSK·컨슈머를 수만 msg/s까지 밀고 EKS HPA로 오토스케일을 시연**한다.

## 1. 타깃 아키텍처
| 컴포넌트 | 서비스/기술 |
|---|---|
| 엣지 시뮬레이터 | EC2 t3.xlarge ×1~3 (Python async + 공유 Producer 풀) |
| 메시지 버스 | **AWS MSK** (provisioned) |
| API Gateway | FastAPI on **EKS** (인증/RateLimit/캐시/사용량) |
| Multi-Agent | LangGraph on EKS (MD/VOC/Insight + Router + Text-to-SQL) |
| 스트림 컨슈머 | EKS Deployments (Review Analyzer, Metric Aggregator, Usage Logger) + **HPA** |
| LLM | **RunPod** vLLM (OpenAI 호환), 외부 |
| DB | **RDS PostgreSQL** |
| 캐시/세션/RateLimit | **ElastiCache Redis** |
| 배치 | **MWAA** (daily DAG) |
| 적재/아티팩트 | S3, ECR, Secrets Manager, ALB |

**데이터 흐름 3종**
- 실시간: `t3.xlarge sim(636+합성, key=seller_id)` → `MSK(order_events / review_created)` → `EKS 컨슈머` → `RDS(review_analysis, daily_*) / Redis`
- 질의: `client → ALB → Gateway(EKS)` → [Redis 캐시 HIT?] → `LangGraph Router → MD/VOC/Insight → Text-to-SQL → RDS(+사전집계) → RunPod(vLLM) → 응답`; 사용량→`model_usage_logs`
- 배치: `MWAA daily DAG` → extract → classify(RunPod) → aggregate → quality_check → load → `RDS daily_category_metrics`

## 2. 엣지노드 시뮬레이터 (핵심 산출물)
- **단위/실행**: state/city 636 base node = async 코루틴, 공유 Producer 풀(코어당 1, 4~8개), 1× t3.xlarge.
- **재생**: 원본 타임스탬프(`order_purchase_timestamp`/`review_creation_date`/`shipping_limit_date`)를 시간순·TAF배 가속 emit, 노드별 독립 시계.
- **메시지**: key=`seller_id`(셀러 순서보장+파티션 분배). payload = 이벤트 필드 + region(state/city) + lat/lng(geolocation 조인 → 지도 시각화).
- **이벤트 타입**: order_created / order_item / payment / review_created (PRD 토픽과 정합).
- **scale 모드(목적 직결)**: 각 도시노드를 ×N(20~200) 합성복제(seller/order id 네임스페이스 분리 + 타임스탬프 지터) → 가상 노드 1.2만~12만개. 고TAF. 단계 ramp **20k→50k→100k msg/s**. 1박스 지속 한계(~3~6만/s, t3 버스트 크레딧 주의) 초과 시 producer EC2 2~3대 수평확장(또는 c6i.xlarge).

## 3. 핵심 의사결정
| 결정 | 선택 | 이유 |
|---|---|---|
| 컴퓨트 | **EKS**(gateway/agent/consumer) + HPA, dev는 docker-compose 로컬 | JD 직격 + scale-demo 핵심(컨슈머 오토스케일 시연). 관리서비스는 EKS 밖 |
| MSK | provisioned **3×kafka.m7g.large**, 3AZ | 파티션/처리량 제어·관측이 scale 시연에 유리(Serverless보다) |
| 토픽/파티션 | order_events **36p**, review_created 12p, review_analyzed 6p, metric_updated 3p; RF=3, retention 1~3d | 컨슈머 병렬성·peak 헤드룸 |
| RunPod | 상시 **Pod**(vLLM/OpenAI호환), 모델 **Qwen2.5-14B/32B-Instruct**(SQL+한국어), GPU A100-80G×1(32B) 또는 L40S(14B) | p95<10s 위해 웜 유지. idle 절감용 Serverless는 옵션 |
| RDS | db.t4g.large, 멀티AZ off(데모), 사전집계 테이블+인덱스 | 분석 p95<10s, 비용 절감 |
| 캐시 | ElastiCache cache.t4g.medium Redis | 캐시/세션/RateLimit 통합, 적중률>30% 목표 |
| 비용 포스처 | 작업/데모 시간만 기동(야간 down) | 포트폴리오 비용 최소화 |

## 4. 수정된 5일 계획
| 일차 | 목표 | 산출물 |
|---|---|---|
| Day 1 | 데이터 레이어 | RDS 프로비저닝, DDL(Olist 8 + 운영 7), CSV→S3→RDS 적재, 인덱스+사전집계 테이블, compose 스캐폴드 |
| Day 2 | AI Gateway | FastAPI, API Key/JWT, Redis RateLimit+캐시, 사용량/비용 로깅, /v1/* 5종, RunPod 클라이언트 |
| Day 3 | Multi-Agent | LangGraph Router, MD/VOC/Insight, Text-to-SQL(읽기전용·LIMIT·검증·self-correct), prompt_versions, 실행 로깅 |
| Day 4 | 스트리밍 | state/city 시뮬레이터(636+합성복제+TAF), MSK 토픽/파티션, 컨슈머(Review Analyzer→review_analysis, Metric Aggregator) |
| Day 5 | 배치·배포·검증 | MWAA daily DAG, EKS 앱티어 배포+HPA, k6 4시나리오+scale ramp, README/다이어그램/데모영상 |

## 5. 비용 개요 (추정, 활성 시간당)
| 서비스 | ~$/hr | 비고 |
|---|---|---|
| MSK 3×m7g.large | ~0.75 | +스토리지 |
| MWAA mw1.small | ~0.49 | 환경 상시 과금 주의 |
| RDS t4g.large | ~0.13 | |
| ElastiCache t4g.medium | ~0.07 | |
| EKS (control+2 노드) | ~0.27 | |
| Producer EC2 t3.xlarge | ~0.17 | scale시 ×2~3 |
| RunPod GPU (A100-80G) | ~1.6~2.5 | Pod 상시 |
| **합계(활성)** | **~$3.5~4.5/hr** | 5일 ~8h/day → 대략 $140~200 (야간 down 기준) |

## 6. Verification
- **시뮬레이터**: 636 base → MSK produce, msg/s·파티션 분포·컨슈머 lag(CloudWatch/kafka-consumer-groups) 확인.
- **scale 데모(핵심)**: 합성복제+고TAF ramp → MSK 처리량 상승 → **EKS HPA가 컨슈머 pod 스케일아웃 → lag 회복** + 동시에 k6 query path **p95<10s·err<1%** 유지 확인.
- **e2e**: review_created → Review Analyzer → review_analysis 적재 → VOC Agent 질의에 반영.
- **k6**: 4시나리오(단순조회/MD/VOC/리뷰대량발행) + stages(0→1000 VU) + thresholds(p95, error_rate, cache_hit).

## 7. JD 토킹포인트
- 대용량·분산: MSK 파티셔닝·핫키(SP 71%) 인지, EKS HPA 오토스케일, k6 수치.
- LLM 운영: Gateway(인증/캐시/RateLimit/비용추적), RunPod 셀프호스팅, prompt versioning.
- 파이프라인: MSK(실시간)+MWAA(배치) 역할 분리.
- 갭 프레이밍: 언어는 Python이나 EKS·Kafka·Redis·Airflow는 회사 스택과 동일, "FDE=문제중심·언어유연".

## 8. 리스크 & 완화
- RunPod 콜드스타트→p95: 상시 Pod. | t3 버스트 크레딧→지속 처리율↓: 피크 짧게/큰 인스턴스/다중 producer.
- EKS 5일 과스코프: dev는 compose, EKS는 Day5 앱티어만(관리서비스 제외). | Text-to-SQL 오류: 읽기전용 role·LIMIT·검증·self-correct.
- MWAA/MSK 상시 비용: 데모 시간만 기동.

## 9. 진행 중 (보정 예정)
백그라운드 설계 워크플로 `woej0pim0`가 서비스별 사이징/비용/DDL/k6 임계치를 정밀화 중 — 완료 시 위 추정치를 교차검증·보정한다(플랜의 구조·결정은 불변).
