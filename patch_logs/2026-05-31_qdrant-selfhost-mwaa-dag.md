# Patch Log — 2026-05-31 · Qdrant 셀프호스트 + MWAA 임베딩 배치 DAG

> RAG "적재" 절반(텍스트 임베딩 → 벡터DB)을 **배치(MWAA)** 경로로 구현. 실시간 컨슈머(`qdrant_loader`)와 같은 sink·모델·NS로 정합(람다 아키텍처).

## 1. 한 일
- **데이터 저장소 정합 확인**: 실물은 **RDS MySQL**(`cj-rds-database-mysql…ap-southeast-2`, MySQL 8.4.8, public). 로컬 Postgres는 시뮬레이터 개발 편의용 — 미사용. olist_raw 8테이블 시드됨(reviews 98,410 / 코멘트 40,659).
- **벡터DB = Qdrant 셀프호스트**: `edge-node-store` EC2(이 박스)에 **systemd 서비스 `qdrant` v1.18.1**(`:6333`, API키). 바이너리 설치, `/opt/qdrant/storage`, API키=`/etc/qdrant/qdrant.env`(600) + `.env`(QDRANT_URL/QDRANT_API_KEY).
- **임베딩 파이프라인**: RDS 리뷰 → fastembed(`paraphrase-multilingual-MiniLM-L12-v2`, 384d, CPU/ONNX) → Qdrant `reviews`. 멱등(point id=uuid5(7b3e NS, review_id)). 샘플 300건 적재 + 의미검색(PT·KR 교차) 검증.
- **MWAA 배치 DAG**: `dags/reviews_embedding_dag.py` (Airflow **3.2.1**, `airflow.sdk`). 무거운 import는 태스크 내부, 시크릿은 Airflow Variable. 로컬 파싱 검증 후 **S3 `dags/` 배포 → MWAA 동기화 완료**(paused).
- **정합**: 병렬 스트리밍 컨슈머(`src/consumers/qdrant_loader.py`)와 **동일 모델(다국어)·NS(7b3e)·컬렉션**으로 통일 → 스트림+배치가 같은 Qdrant `reviews`에 멱등 적재.

## 2. 인프라 사실
| 자원 | 값 |
|---|---|
| MWAA | `cj-airflow` AVAILABLE, Airflow 3.2.1, mw1.small, 서울 vpc-0962, NAT egress 있음(EIP 54.116.185.212 / 3.39.208.251) |
| DAG S3 | `s3://cj-airflow-231143200487-ap-northeast-2-an/dags/` |
| Qdrant | edge-node-store EC2(i-00c4c6bf26bae1344, vpc-0113, public 43.202.253.112), `:6333`, sg-063f3cc84567cdaa6 |
| 교차리전 | MSK·MWAA=서울 / RDS=시드니 → MWAA→RDS는 public+egress로 접속 |

## 3. 남은 작업 (MWAA에서 DAG 실제 실행)
1. **SG 6333 개방** — 이 박스 sg에 인바운드 TCP 6333을 MWAA NAT EIP 2개(/32)로 한정.
2. **Airflow Variables** — MYSQL_*, QDRANT_URL=`http://43.202.253.112:6333`(public), QDRANT_API_KEY.
3. **requirements.txt → S3 + 환경 업데이트**(pymysql·qdrant-client·fastembed) — ~20–30분(MWAA 일시 불가). mw1.small에서 fastembed 메모리 주의.
4. **unpause + 트리거 → 검증**(Qdrant 포인트 증가).

## 4. 비고
- 두 세션(배치=이 작업 / 스트리밍+vLLM=병렬)이 같은 레포 동시 작업 — 공유 RAG 파일은 병렬 세션이 소유, 본 작업은 MWAA 레인에 집중.
