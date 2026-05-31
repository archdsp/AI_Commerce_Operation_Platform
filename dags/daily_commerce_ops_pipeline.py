"""일별 카테고리 집계 배치 DAG — AWS MWAA (Airflow 3.2.1). [PRD: daily_commerce_ops_pipeline]

스트리밍 Metric Aggregator(`src/consumers/metric_aggregator.py`)와 **동일 정의**로
`commerce_ops.daily_category_metrics`를 **전체 재계산**한다 = 람다 아키텍처의 **배치 arm(확정값)**.
스트림은 영향 날짜만 근사 갱신, 배치는 모든 (날짜×카테고리)를 재계산해 누락/유실을 보정.

- 집계 기준: 리뷰된 주문, `metric_date = review_analysis.sim_review_date`, 카테고리별.
- 멱등: UPSERT (metric_date, category_name_en) — 스트림/배치가 같은 행으로 수렴.
- 의존성: **pymysql만**(경량 → mw1.small에 안전하게 설치). 임베딩(fastembed)은 스트리밍 컨슈머 담당.
- 시크릿/설정: Airflow Variable `MYSQL_HOST/MYSQL_PORT/MYSQL_USER/MYSQL_PASSWORD`.
"""
from __future__ import annotations

import pendulum
from airflow.sdk import dag, task

# 스트리밍 Aggregator(AGG_SQL)와 동일한 카테고리/지표 정의. 차이는 "전체 재계산"(날짜 필터 없음).
_CAT = "COALESCE(ct.product_category_name_english, p.product_category_name, 'unknown')"
RECOMPUTE_SQL = f"""
INSERT INTO commerce_ops.daily_category_metrics
  (metric_date, category_name_en, gmv, order_count, units_sold, avg_review_score,
   negative_review_count, voc_quality_count, voc_delivery_count, loaded_at)
SELECT ra.sim_review_date, {_CAT},
       ROUND(SUM(oi.price),2), COUNT(DISTINCT ra.order_id), COUNT(*),
       ROUND(AVG(ra.review_score),3),
       COUNT(DISTINCT CASE WHEN ra.sentiment='negative' THEN ra.review_id END),
       COUNT(DISTINCT CASE WHEN ra.voc_category='quality'  THEN ra.review_id END),
       COUNT(DISTINCT CASE WHEN ra.voc_category='delivery' THEN ra.review_id END),
       NOW()
FROM commerce_ops.review_analysis ra
JOIN olist_raw.order_items oi ON oi.order_id = ra.order_id
JOIN olist_raw.products p     ON p.product_id = oi.product_id
LEFT JOIN olist_raw.category_translation ct ON ct.product_category_name = p.product_category_name
WHERE ra.sim_review_date IS NOT NULL
GROUP BY ra.sim_review_date, {_CAT}
ON DUPLICATE KEY UPDATE
  gmv=VALUES(gmv), order_count=VALUES(order_count), units_sold=VALUES(units_sold),
  avg_review_score=VALUES(avg_review_score), negative_review_count=VALUES(negative_review_count),
  voc_quality_count=VALUES(voc_quality_count), voc_delivery_count=VALUES(voc_delivery_count), loaded_at=NOW()
"""


def _connect():
    import pymysql
    from airflow.sdk import Variable
    return pymysql.connect(
        host=Variable.get("MYSQL_HOST"), port=int(Variable.get("MYSQL_PORT", default="3306")),
        user=Variable.get("MYSQL_USER"), password=Variable.get("MYSQL_PASSWORD"),
        connect_timeout=20, autocommit=False)  # 스키마 무지정 — SQL이 fully-qualified


@dag(
    dag_id="daily_commerce_ops_pipeline",
    schedule="@daily",
    start_date=pendulum.datetime(2026, 5, 1, tz="UTC"),
    catchup=False,
    tags=["commerce", "batch", "metrics"],
    doc_md=__doc__,
)
def daily_commerce_ops_pipeline():

    @task
    def aggregate_daily_metrics() -> dict:
        import logging
        log = logging.getLogger("airflow.task")
        con = _connect()
        try:
            with con.cursor() as cur:
                affected = cur.execute(RECOMPUTE_SQL)
            con.commit()
        finally:
            con.close()
        log.info("daily_category_metrics 전체 재계산 UPSERT (affected≈%s)", affected)
        return {"affected": affected}

    @task
    def quality_check(agg: dict) -> dict:
        import logging
        log = logging.getLogger("airflow.task")
        con = _connect()
        try:
            with con.cursor() as cur:
                cur.execute("SELECT COUNT(*), COUNT(DISTINCT metric_date), MIN(gmv), MIN(order_count) "
                            "FROM commerce_ops.daily_category_metrics")
                rows, days, min_gmv, min_oc = cur.fetchone()
        finally:
            con.close()
        log.info("QC rows=%s days=%s min_gmv=%s min_order=%s", rows, days, min_gmv, min_oc)
        if not rows:
            raise ValueError("daily_category_metrics 비어있음 — 집계 실패(게이트)")
        if (min_gmv is not None and min_gmv < 0) or (min_oc is not None and min_oc < 0):
            raise ValueError(f"음수 지표 발견 gmv={min_gmv} order={min_oc} (게이트)")
        return {"rows": rows, "days": days}

    quality_check(aggregate_daily_metrics())


daily_commerce_ops_pipeline()
