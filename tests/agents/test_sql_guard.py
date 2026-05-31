"""Text-to-SQL 가드레일 — SELECT only · 화이트리스트 · 블랙리스트 · 자동 LIMIT."""
import pytest

from agents.sql_guard import SQLRejected, guard


def test_select_ok_and_autolimit():
    out = guard("SELECT category_name_en, SUM(gmv) AS g FROM commerce_ops.daily_category_metrics GROUP BY category_name_en")
    assert "limit" in out.lower()                 # LIMIT 자동 추가
    assert "daily_category_metrics" in out


def test_join_whitelist_ok():
    out = guard("SELECT ra.review_id FROM commerce_ops.review_analysis ra "
                "JOIN olist_raw.reviews r ON r.review_id=ra.review_id "
                "WHERE ra.sentiment='negative' LIMIT 5")
    assert "review_analysis" in out and "reviews" in out


@pytest.mark.parametrize("sql", [
    "DROP TABLE commerce_ops.review_analysis",
    "SELECT * FROM information_schema.tables",
    "UPDATE commerce_ops.review_analysis SET sentiment='x'",
    "DELETE FROM olist_raw.orders",
])
def test_dangerous_rejected(sql):
    with pytest.raises(SQLRejected):
        guard(sql)


def test_non_whitelist_table_rejected():
    with pytest.raises(SQLRejected):
        guard("SELECT * FROM olist_raw.secret_table LIMIT 1")


def test_schema_prefix_required():
    # 스키마 접두 없는 테이블은 거부
    with pytest.raises(SQLRejected):
        guard("SELECT * FROM daily_category_metrics LIMIT 1")
