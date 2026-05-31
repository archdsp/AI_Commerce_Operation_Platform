"""RDS MySQL 연결 헬퍼 (pymysql). .env 의 MYSQL_* 사용.

두 스키마(olist_raw, commerce_ops)는 같은 서버의 데이터베이스이므로,
연결 1개로 `olist_raw.x`·`commerce_ops.y` 교차 스키마 조인이 가능하다.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pymysql
from dotenv import load_dotenv
from pymysql.err import OperationalError

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

OLIST_DB = os.environ.get("MYSQL_DB_OLIST", "olist_raw")
OPS_DB = os.environ.get("MYSQL_DB_OPS", "commerce_ops")


def mysql_conn(database: str | None = None, autocommit: bool = False) -> "pymysql.connections.Connection":
    return pymysql.connect(
        host=os.environ["MYSQL_HOST"],
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=database,
        autocommit=autocommit,
        charset="utf8mb4",
        connect_timeout=15,
        read_timeout=120,
        write_timeout=120,
    )


def commit_with_retry(conn, work, retries: int = 4) -> None:
    """work() 실행 후 commit. InnoDB 데드락(1213)/락 타임아웃(1205) 시 롤백 후 재시도.

    교차리전 + 동시 컨슈머(분석기 쓰기 ↔ 집계기 읽기)에서 발생하는 일시적 데드락 대응.
    work는 멱등(UPSERT)이어야 안전하게 재시도 가능.
    """
    for attempt in range(retries):
        try:
            work()
            conn.commit()
            return
        except OperationalError as exc:
            code = exc.args[0] if exc.args else None
            if code in (1213, 1205) and attempt < retries - 1:
                conn.rollback()
                time.sleep(0.1 * (attempt + 1))
                continue
            raise
