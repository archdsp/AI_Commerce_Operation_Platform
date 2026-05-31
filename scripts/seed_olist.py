#!/usr/bin/env python3
"""Olist CSV → olist_raw 대량 적재 (psycopg2 COPY).

FK 의존 순서 준수. reviews는 원본에 review_id 중복이 있어 staging→DISTINCT ON 후 적재.
환경변수: PGHOST/PGPORT/PGUSER/PGPASSWORD, DATA_DIR, OLIST_DB(기본 olist_raw).
"""
import os
import sys
import psycopg2

DATA_DIR = os.environ.get("DATA_DIR", "../data")
DSN = dict(
    host=os.environ.get("PGHOST", "localhost"),
    port=os.environ.get("PGPORT", "5432"),
    user=os.environ.get("PGUSER", "postgres"),
    password=os.environ.get("PGPASSWORD", "postgres"),
    dbname=os.environ.get("OLIST_DB", "olist_raw"),
)

# (table, csv) — FK 의존 순서 (reviews는 별도 dedupe 처리)
LOAD = [
    ("category_translation", "product_category_name_translation.csv"),
    ("customers",   "olist_customers_dataset.csv"),
    ("sellers",     "olist_sellers_dataset.csv"),
    ("products",    "olist_products_dataset.csv"),
    ("orders",      "olist_orders_dataset.csv"),
    ("order_items", "olist_order_items_dataset.csv"),
    ("payments",    "olist_order_payments_dataset.csv"),
]


def copy_csv(cur, table, path):
    with open(path, "r", encoding="utf-8") as f:
        cur.copy_expert(
            f"COPY {table} FROM STDIN WITH (FORMAT csv, HEADER true)", f
        )


def main():
    if not os.path.isdir(DATA_DIR):
        sys.exit(f"DATA_DIR not found: {DATA_DIR}")
    conn = psycopg2.connect(**DSN)
    conn.autocommit = False
    cur = conn.cursor()

    # 역순 TRUNCATE(자식부터) — 멱등 재적재
    for table, _ in reversed(LOAD):
        cur.execute(f"TRUNCATE {table} CASCADE")
    cur.execute("TRUNCATE reviews CASCADE")

    for table, csv in LOAD:
        copy_csv(cur, table, os.path.join(DATA_DIR, csv))
        print(f"  loaded {table}")

    # reviews: review_id 중복 제거
    cur.execute("CREATE TEMP TABLE reviews_stg (LIKE reviews) ON COMMIT DROP")
    with open(os.path.join(DATA_DIR, "olist_order_reviews_dataset.csv"), encoding="utf-8") as f:
        cur.copy_expert("COPY reviews_stg FROM STDIN WITH (FORMAT csv, HEADER true)", f)
    cur.execute(
        """
        INSERT INTO reviews
        SELECT DISTINCT ON (review_id) *
        FROM reviews_stg
        ORDER BY review_id, review_creation_date DESC NULLS LAST
        ON CONFLICT (review_id) DO NOTHING
        """
    )
    print(f"  loaded reviews (deduped → {cur.rowcount} rows)")

    conn.commit()

    print("\n=== row counts ===")
    for t in [x[0] for x in LOAD] + ["reviews"]:
        cur.execute(f"SELECT count(*) FROM {t}")
        print(f"  {t:24} {cur.fetchone()[0]:>8}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
