# 03. 데이터베이스 (PostgreSQL / RDS)

## 구성요소
2개 DB — `olist_raw`(원본 8테이블), `commerce_ops`(운영 7테이블: api_keys/agent_requests/agent_executions/prompt_versions/model_usage_logs/review_analysis/daily_category_metrics). Agent·Airflow·분석이 사용. (시뮬레이터 자체는 DB 불필요 — CSV 샤드만 사용)

## 옵션 A — 로컬 PostgreSQL (개발/검증)
```bash
sudo apt-get install -y postgresql postgresql-client
sudo service postgresql start
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres';"

export PGHOST=localhost PGUSER=postgres PGPASSWORD=postgres
export DATA_DIR=$OLIST_DATA_DIR
bash scripts/setup_db.sh        # DB 2개 생성 → 스키마 → readonly grant → CSV 적재 → 부트스트랩
```

## 옵션 B — AWS RDS PostgreSQL
```bash
aws rds create-db-instance --db-instance-identifier cj-commerce \
  --engine postgres --engine-version 16 --db-instance-class db.t4g.small \
  --allocated-storage 20 --master-username postgres --master-user-password '<PW>' \
  --vpc-security-group-ids sg-xxxx --no-publicly-accessible --region ap-northeast-2
# 엔드포인트 확인
aws rds describe-db-instances --db-instance-identifier cj-commerce \
  --query 'DBInstances[0].Endpoint.Address' --output text

export PGHOST=<rds-endpoint> PGUSER=postgres PGPASSWORD='<PW>' DATA_DIR=$OLIST_DATA_DIR
bash scripts/setup_db.sh
```
> RDS 보안그룹 5432 인바운드 허용 + 같은 VPC. 데모는 Single-AZ/db.t4g.small로 충분.

## 스키마·적재 산출물
| 파일 | 내용 |
|------|------|
| `db/schema/olist_raw/001_tables.sql` | Olist 8테이블 + 인덱스 |
| `db/schema/commerce_ops/001_tables.sql` | 운영 7테이블 + 인덱스 |
| `scripts/seed_olist.py` | CSV→DB COPY (reviews 중복 dedup) |
| `db/seed/commerce_ops/20_bootstrap.sql` | 기본 프롬프트 5종 + 데모 api_keys |

## 검증
```bash
psql -h $PGHOST -U postgres -d olist_raw -c "select count(*) from order_items;"   # 112650
psql -h $PGHOST -U postgres -d commerce_ops -c "select agent_type from prompt_versions;"
```

> 다음: [04_msk.md](./04_msk.md)
