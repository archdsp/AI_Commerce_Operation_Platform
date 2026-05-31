"""Text-to-SQL 가드레일 (docs/AGENTS.md §4) — SELECT only · 화이트리스트 · 블랙리스트 · 자동 LIMIT.

sqlglot(MySQL 방언)으로 파싱·검증. 통과 시 안전한 SQL 문자열 반환, 위반 시 SQLRejected.
"""
from __future__ import annotations

import re

import sqlglot
from sqlglot import exp

WHITELIST = {
    "olist_raw.customers", "olist_raw.orders", "olist_raw.order_items", "olist_raw.products",
    "olist_raw.reviews", "olist_raw.payments", "olist_raw.sellers", "olist_raw.category_translation",
    "commerce_ops.daily_category_metrics", "commerce_ops.review_analysis",
}
_BLACKLIST = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|REPLACE|MERGE|CALL|"
    r"information_schema|performance_schema|mysql|sys|sleep|benchmark|load_file|outfile)\b",
    re.IGNORECASE,
)


class SQLRejected(Exception):
    pass


def guard(sql: str, max_rows: int = 100) -> str:
    sql = (sql or "").strip().rstrip(";").strip()
    if not sql:
        raise SQLRejected("빈 SQL")
    if _BLACKLIST.search(sql):
        raise SQLRejected("금지 키워드 포함")
    try:
        parsed = sqlglot.parse_one(sql, read="mysql")
    except Exception as exc:  # noqa: BLE001
        raise SQLRejected(f"파싱 실패: {exc}")
    if not isinstance(parsed, exp.Select):
        raise SQLRejected("SELECT 문만 허용")

    for table in parsed.find_all(exp.Table):
        name = (f"{table.db}." if table.db else "") + table.name
        if name.lower() not in WHITELIST:
            raise SQLRejected(f"비허용 테이블: {name or table.name} (스키마 접두 필수)")

    if not parsed.args.get("limit"):
        parsed = parsed.limit(max_rows)
    return parsed.sql(dialect="mysql")
