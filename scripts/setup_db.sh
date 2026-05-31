#!/usr/bin/env bash
# 로컬/컨테이너 Postgres에 2개 DB 구축: 생성 → 스키마 → readonly grant → Olist 적재 → bootstrap
# 사용: PGHOST=... PGUSER=... DATA_DIR=... scripts/setup_db.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PGHOST="${PGHOST:-localhost}"
export PGPORT="${PGPORT:-5432}"
export PGUSER="${PGUSER:-postgres}"
export PGPASSWORD="${PGPASSWORD:-postgres}"
export DATA_DIR="${DATA_DIR:-$ROOT/../data}"

echo "[1/5] 데이터베이스/롤 생성"
psql -v ON_ERROR_STOP=1 -d postgres -f "$ROOT/db/init/00_create_databases.sql"
psql -v ON_ERROR_STOP=1 -d postgres -f "$ROOT/db/init/01_roles.sql"

echo "[2/5] 스키마 적용"
psql -v ON_ERROR_STOP=1 -d olist_raw    -f "$ROOT/db/schema/olist_raw/001_tables.sql"
psql -v ON_ERROR_STOP=1 -d commerce_ops -f "$ROOT/db/schema/commerce_ops/001_tables.sql"

echo "[3/5] readonly(GRANT) — Text-to-SQL 격리"
for db in olist_raw commerce_ops; do
  psql -v ON_ERROR_STOP=1 -d "$db" -c \
    "GRANT USAGE ON SCHEMA public TO t2s_readonly;
     GRANT SELECT ON ALL TABLES IN SCHEMA public TO t2s_readonly;
     ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO t2s_readonly;"
done

echo "[4/5] Olist 적재"
python3 "$ROOT/scripts/seed_olist.py"

echo "[5/5] commerce_ops 부트스트랩"
psql -v ON_ERROR_STOP=1 -d commerce_ops -f "$ROOT/db/seed/commerce_ops/20_bootstrap.sql"

echo "DONE ✅"
