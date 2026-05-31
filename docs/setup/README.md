# 셋업 가이드 — Kaggle 데이터 → AWS

논리적 **구성요소 단위**로 분리했습니다. 1→5 순서로 진행하세요.

| # | 구성요소 | 문서 | 상태 |
|---|----------|------|------|
| 1 | 데이터 (Kaggle Olist) | [01_data_kaggle.md](./01_data_kaggle.md) | ✅ 구현 |
| 2 | Python 환경 | [02_python_env.md](./02_python_env.md) | ✅ 구현 |
| 3 | 데이터베이스 (PostgreSQL / RDS) | [03_database.md](./03_database.md) | ✅ 구현 |
| 4 | 메시징 (AWS MSK Serverless) | [04_msk.md](./04_msk.md) | ✅ 구현 |
| 5 | 엣지 점포 시뮬레이터 | [05_edge_simulator.md](./05_edge_simulator.md) | ✅ 구현·검증 |
| 6 | Gateway · Agents · Consumers · Airflow · 배포 | (예정) | ⏳ 미구현 |

## 구성요소 의존 관계
```text
Kaggle CSV ──(적재)──> PostgreSQL(olist_raw, commerce_ops)
          └─(분할)──> data/edges/*.jsonl ──(발행)──> AWS MSK ──(소비, 예정)──> commerce_ops
```

## 최소 경로 (시뮬레이터까지)
```bash
# 1) 데이터
kaggle datasets download -d olistbr/brazilian-ecommerce -p $OLIST_DATA_DIR --unzip
# 2) 환경
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env   # 값 편집
# 3) DB (선택, Agent용)
bash scripts/setup_db.sh
# 4) MSK 토픽
python scripts/kafka_admin.py --create
# 5) 시뮬레이터
python scripts/prepare_edges.py      # CSV → 636 점포 샤드
python scripts/run.py                # 샤드 → MSK 발행
python scripts/consume_check.py --sample 3
```

> 로그는 `/workspace/app_logs/{app_name}/` (시뮬레이터는 `edge_simulator`)에 남습니다. `APP_LOG_DIR`로 변경 가능.
