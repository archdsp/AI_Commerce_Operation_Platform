#!/usr/bin/env python3
"""풀 Olist CSV → 참조무결성 유지 **소형 샘플** 생성 (`data/olist_sample/`).

로컬 모드(맥북 · WSL Ubuntu · Windows)에서 AWS·Kaggle 없이 자급형 데모를 돌리기 위한
**결정론적** 샘플 데이터셋. `setup_mysql.py`(olist_raw 적재)와 `prepare_edges.py`(엣지 샤드)가
**같은 파일명**을 읽으므로, 이 디렉터리를 `OLIST_DATA_DIR`로 가리키면 양쪽 모두 동작한다.

  python scripts/make_local_sample.py --src /path/to/olist_full --orders 5000

표본 기준(결정론적): order_items와 reviews에 **모두** 등장하는 주문을 order_id 정렬 후 앞에서 N건.
→ 이후 참조되는 products/sellers/customers/payments만 필터링, category_translation은 전체 보존.
이렇게 하면 같은 order_id 집합이 olist_raw와 스트림 이벤트 양쪽에 존재 → metric_aggregator의
교차스키마 조인(commerce_ops.review_analysis ⋈ olist_raw.order_items ⋈ products)이 성립한다.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]

# 논리명 → Olist 원본 파일명 (setup_mysql.py / prepare_edges.py와 동일)
FILES = {
    "orders":    "olist_orders_dataset.csv",
    "items":     "olist_order_items_dataset.csv",
    "reviews":   "olist_order_reviews_dataset.csv",
    "products":  "olist_products_dataset.csv",
    "sellers":   "olist_sellers_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "payments":  "olist_order_payments_dataset.csv",
    "category":  "product_category_name_translation.csv",
}

# 풀 데이터셋 자동 탐색 후보 (이 머신/일반적 위치)
SRC_CANDIDATES = [
    REPO / "data" / "olist",
    REPO / ".." / "data",
    REPO / ".." / ".." / "data",
    REPO / ".." / ".." / ".." / "data",
    Path.home() / "olist",
    Path.home() / "data" / "olist",
]


def _find_src(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if (p / FILES["orders"]).exists():
            return p
        raise SystemExit(f"--src 경로에 Olist CSV가 없습니다: {p}")
    for cand in SRC_CANDIDATES:
        cand = cand.resolve()
        if (cand / FILES["orders"]).exists():
            return cand
    raise SystemExit(
        "풀 Olist CSV 디렉터리를 찾을 수 없습니다. --src 로 지정하세요 "
        "(9개 CSV: olist_orders_dataset.csv 등)."
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Olist 풀 CSV → 소형 로컬 샘플 생성")
    ap.add_argument("--src", default=None, help="풀 Olist CSV 디렉터리 (미지정 시 자동 탐색)")
    ap.add_argument("--out", default=str(REPO / "data" / "olist_sample"), help="샘플 출력 디렉터리")
    ap.add_argument("--orders", type=int, default=5000, help="표본 주문 수 (기본 5000)")
    args = ap.parse_args()

    src = _find_src(args.src)
    out = Path(args.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    print(f"src = {src}\nout = {out}\norders = {args.orders}\n")

    def rd(key: str) -> pd.DataFrame:
        return pd.read_csv(src / FILES[key], dtype=str, encoding="utf-8-sig")

    orders = rd("orders")
    items = rd("items")
    reviews = rd("reviews").drop_duplicates(subset="review_id", keep="first")

    # order_items와 reviews 모두에 있는 주문만 → 결정론적으로 앞에서 N건
    candidates = sorted(set(items["order_id"]) & set(reviews["order_id"]))
    keep_orders = set(candidates[: args.orders])
    if not keep_orders:
        raise SystemExit("교집합 주문이 없습니다 — 입력 데이터를 확인하세요.")

    orders_s = orders[orders["order_id"].isin(keep_orders)]
    items_s = items[items["order_id"].isin(keep_orders)]
    reviews_s = reviews[reviews["order_id"].isin(keep_orders)]
    payments_s = rd("payments")
    payments_s = payments_s[payments_s["order_id"].isin(keep_orders)]

    products_s = rd("products")
    products_s = products_s[products_s["product_id"].isin(set(items_s["product_id"]))]
    sellers_s = rd("sellers")
    sellers_s = sellers_s[sellers_s["seller_id"].isin(set(items_s["seller_id"]))]
    customers_s = rd("customers")
    customers_s = customers_s[customers_s["customer_id"].isin(set(orders_s["customer_id"]))]
    category = rd("category")  # 전체 보존 (71행, 매핑 무결성)

    out_frames = {
        "orders": orders_s, "items": items_s, "reviews": reviews_s, "payments": payments_s,
        "products": products_s, "sellers": sellers_s, "customers": customers_s, "category": category,
    }
    total_bytes = 0
    for key, df in out_frames.items():
        path = out / FILES[key]
        df.to_csv(path, index=False, encoding="utf-8")
        total_bytes += path.stat().st_size
        print(f"  {FILES[key]:48} {len(df):>7,} rows  ({path.stat().st_size/1024:,.0f} KB)")
    print(f"\n샘플 생성 완료 → {out}  (총 {total_bytes/1024/1024:.1f} MB)")


if __name__ == "__main__":
    main()
