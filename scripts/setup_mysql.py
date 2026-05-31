#!/usr/bin/env python3
"""RDS MySQL 초기화 — 스키마 적용(olist_raw, commerce_ops) + Olist CSV 적재.

  python scripts/setup_mysql.py
.env 의 MYSQL_* / OLIST_DATA_DIR 사용. 멱등(TRUNCATE 후 재적재).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from common.db import OLIST_DB, mysql_conn
from edge_simulator.config import data_dir
from edge_simulator.logging_setup import setup_logging

logger = setup_logging("setup_mysql")
SCHEMA = Path(__file__).resolve().parents[1] / "db" / "schema" / "mysql"
BATCH = 2000

INT_COLS = {"order_item_id", "payment_sequential", "payment_installments", "review_score",
            "product_name_lenght", "product_description_lenght", "product_photos_qty",
            "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"}
DEC_COLS = {"price", "freight_value", "payment_value"}

LOAD = [
    ("category_translation", "product_category_name_translation.csv"),
    ("customers", "olist_customers_dataset.csv"),
    ("sellers", "olist_sellers_dataset.csv"),
    ("products", "olist_products_dataset.csv"),
    ("orders", "olist_orders_dataset.csv"),
    ("order_items", "olist_order_items_dataset.csv"),
    ("payments", "olist_order_payments_dataset.csv"),
]


def _apply_sql(cur, path: Path) -> None:
    for chunk in path.read_text(encoding="utf-8").split(";"):
        body = "\n".join(ln for ln in chunk.splitlines() if not ln.strip().startswith("--")).strip()
        if body:
            cur.execute(body)


def _cast(col: str, val):
    if val is None or val == "" or (isinstance(val, float) and pd.isna(val)):
        return None
    if col in INT_COLS:
        return int(float(val))
    if col in DEC_COLS:
        return float(val)
    return val


def _insert(conn, db: str, table: str, df: pd.DataFrame) -> int:
    cols = list(df.columns)
    rows = [tuple(_cast(c, v) for c, v in zip(cols, r)) for r in df.itertuples(index=False)]
    placeholders = ",".join(["%s"] * len(cols))
    sql = f"INSERT INTO {db}.{table} ({','.join(cols)}) VALUES ({placeholders})"
    with conn.cursor() as cur:
        cur.execute(f"TRUNCATE {db}.{table}")
        for i in range(0, len(rows), BATCH):
            cur.executemany(sql, rows[i:i + BATCH])
    conn.commit()
    logger.info("  {}.{} ← {:,} rows", db, table, len(rows))
    return len(rows)


def main() -> None:
    dd = data_dir()
    conn = mysql_conn(autocommit=False)
    logger.info("스키마 적용 (olist_raw, commerce_ops)")
    with conn.cursor() as cur:
        _apply_sql(cur, SCHEMA / "olist_raw.sql")
        _apply_sql(cur, SCHEMA / "commerce_ops.sql")
    conn.commit()

    logger.info("Olist 적재 → {} (from {})", OLIST_DB, dd)
    for table, csv in LOAD:
        _insert(conn, OLIST_DB, table, pd.read_csv(dd / csv, dtype=str, encoding="utf-8-sig"))
    reviews = (pd.read_csv(dd / "olist_order_reviews_dataset.csv", dtype=str, encoding="utf-8-sig")
               .drop_duplicates(subset="review_id", keep="first"))
    _insert(conn, OLIST_DB, "reviews", reviews)

    with conn.cursor() as cur:
        logger.info("=== row counts ===")
        for t in [x[0] for x in LOAD] + ["reviews"]:
            cur.execute(f"SELECT COUNT(*) FROM {OLIST_DB}.{t}")
            logger.info("  {:24} {:>8,}", t, cur.fetchone()[0])
    conn.close()
    logger.success("RDS MySQL 초기화 완료")


if __name__ == "__main__":
    main()
