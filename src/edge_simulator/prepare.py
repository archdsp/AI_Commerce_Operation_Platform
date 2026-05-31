"""Olist CSV → 점포(엣지노드)별 데이터 샤드 생성.

엣지노드 = (seller_state, seller_city) [state_city] 또는 seller_id [seller].
무거운 조인/파싱을 1회만 수행하고 노드별 JSONL 샤드 + manifest.json을 결정론적으로 남긴다.
샤드 한 줄 = 그대로 발행할 레코드 {"key","kind","ts","value":{봉투}}.
"""
from __future__ import annotations

import json
import re
import uuid
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

import pandas as pd
from loguru import logger

# 결정론적 event_id 네임스페이스 (고정)
EVENT_NS = uuid.UUID("0b3e6a52-2f7a-4c9b-9b1e-2a1d3c4f5e6a")
_DEFAULT_TS = pd.Timestamp("2017-01-01", tz="UTC")


def slug(value: str) -> str:
    """파일명용 슬러그 (영숫자 외 → _)."""
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_") or "na"


def vec_ts(series: pd.Series) -> pd.Series:
    """컬럼 단위 벡터화 타임스탬프 파싱 (NaT → 기본값). 행별 파싱 대비 ~100x 빠름."""
    return pd.to_datetime(series, utc=True, errors="coerce").fillna(_DEFAULT_TS)


def event_id(event_type: str, natural: str) -> str:
    """동일 입력 → 동일 event_id (재현·멱등 보장)."""
    return str(uuid.uuid5(EVENT_NS, f"{event_type}:{natural}"))


def build(data_dir: Path, granularity: str = "state_city", events: str = "all"):
    """노드별 이벤트(시프트 전) 리스트 생성. 반환 (node_rows, by_type, max_ts)."""
    data_dir = Path(data_dir)
    sellers = pd.read_csv(data_dir / "olist_sellers_dataset.csv", dtype=str)
    orders = pd.read_csv(data_dir / "olist_orders_dataset.csv", dtype=str)
    items = pd.read_csv(data_dir / "olist_order_items_dataset.csv", dtype=str)
    reviews = pd.read_csv(data_dir / "olist_order_reviews_dataset.csv", dtype=str)

    sellers["seller_state"] = sellers["seller_state"].str.strip()
    sellers["seller_city"] = sellers["seller_city"].str.strip().str.lower()

    def node_of(state: str, city: str, seller_id: str) -> str:
        return seller_id if granularity == "seller" else f"{state}|{city}"

    seller_node = {
        r.seller_id: node_of(r.seller_state, r.seller_city, r.seller_id)
        for r in sellers.itertuples(index=False)
    }
    seller_geo = sellers.set_index("seller_id")[["seller_state", "seller_city"]].to_dict("index")
    order_purchase = dict(zip(orders["order_id"], vec_ts(orders["order_purchase_timestamp"])))
    order_primary_seller: dict[str, str] = {}
    for r in items.itertuples(index=False):
        order_primary_seller.setdefault(r.order_id, r.seller_id)

    want_orders = events in ("all", "orders")
    want_reviews = events in ("all", "reviews")
    node_rows: dict[str, list[dict]] = defaultdict(list)
    by_type: dict[str, int] = defaultdict(int)
    max_ts = pd.Timestamp("2016-01-01", tz="UTC")

    if want_orders:
        item_ts = vec_ts(items["shipping_limit_date"]).tolist()
        for i, r in enumerate(items.itertuples(index=False)):
            node = seller_node.get(r.seller_id)
            if node is None:
                continue
            ts = order_purchase.get(r.order_id, item_ts[i])
            max_ts = max(max_ts, ts)
            geo = seller_geo.get(r.seller_id, {})
            node_rows[node].append({
                "ts": ts, "key": r.seller_id, "kind": "order", "event_type": "order_item",
                "natural": f"{r.order_id}:{r.order_item_id}",
                "payload": {
                    "order_id": r.order_id, "order_item_id": int(r.order_item_id),
                    "seller_id": r.seller_id, "product_id": r.product_id,
                    "price": float(r.price), "freight_value": float(r.freight_value),
                    "seller_state": geo.get("seller_state"), "seller_city": geo.get("seller_city"),
                },
            })
            by_type["order_item"] += 1

    if want_reviews:
        rev_ts = vec_ts(reviews["review_creation_date"]).tolist()
        seen: set[str] = set()
        for i, r in enumerate(reviews.itertuples(index=False)):
            if r.review_id in seen:
                continue
            seen.add(r.review_id)
            seller = order_primary_seller.get(r.order_id)
            node = seller_node.get(seller) if seller else None
            if node is None:
                continue
            ts = rev_ts[i]
            max_ts = max(max_ts, ts)
            geo = seller_geo.get(seller, {})
            node_rows[node].append({
                "ts": ts, "key": seller, "kind": "review", "event_type": "review_created",
                "natural": r.review_id,
                "payload": {
                    "review_id": r.review_id, "order_id": r.order_id,
                    "review_score": None if pd.isna(r.review_score) else int(r.review_score),
                    "review_comment_title": None if pd.isna(r.review_comment_title) else r.review_comment_title,
                    "review_comment_message": None if pd.isna(r.review_comment_message) else r.review_comment_message,
                    "seller_id": seller,
                    "seller_state": geo.get("seller_state"), "seller_city": geo.get("seller_city"),
                    "source": "simulator",
                },
            })
            by_type["review_created"] += 1

    logger.info("build: 노드 {} | 이벤트 {} {}", len(node_rows), sum(by_type.values()), dict(by_type))
    return node_rows, dict(by_type), max_ts


def write_shards(node_rows, by_type, max_ts, out_dir: Path, sim_today: pd.Timestamp,
                 granularity: str, events: str) -> dict:
    """노드별 JSONL 샤드 + manifest.json 작성. 반환 manifest dict."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob("*.jsonl"):     # 재현: 기존 샤드 정리
        f.unlink()

    shift = timedelta(days=(sim_today.date() - max_ts.date()).days)
    logger.info("shift {}일 → SIM_TODAY {}", shift.days, sim_today.date())

    shards = []
    used: dict[str, int] = {}
    for node_key, rows in sorted(node_rows.items()):
        rows.sort(key=lambda r: (r["ts"], r["event_type"]))
        base = slug(node_key.replace("|", "__"))
        used[base] = used.get(base, -1) + 1
        fname = base if used[base] == 0 else f"{base}_{used[base]}"
        path = out_dir / f"{fname}.jsonl"

        et: dict[str, int] = defaultdict(int)
        with path.open("w", encoding="utf-8") as fh:
            for r in rows:
                occurred = (r["ts"] + shift)
                payload = dict(r["payload"])
                if r["event_type"] == "review_created":
                    payload["sim_review_date"] = occurred.date().isoformat()
                value = {
                    "event_id": event_id(r["event_type"], r["natural"]),
                    "event_type": r["event_type"],
                    "occurred_at": occurred.isoformat(),
                    "payload": payload,
                }
                fh.write(json.dumps(
                    {"key": r["key"], "kind": r["kind"], "ts": r["ts"].isoformat(), "value": value},
                    ensure_ascii=False) + "\n")
                et[r["event_type"]] += 1

        shards.append({
            "node_key": node_key, "file": path.name, "events": len(rows),
            "sellers": len({r["key"] for r in rows}), "by_type": dict(et),
            "ts_start": min(r["ts"] for r in rows).isoformat(),
            "ts_end": max(r["ts"] for r in rows).isoformat(),
        })

    manifest = {
        "generated_for": "olist-edge-simulator",
        "granularity": granularity,
        "sim_today": sim_today.date().isoformat(),
        "shift_days": shift.days,
        "nodes": len(shards),
        "total_events": sum(by_type.values()),
        "by_type": by_type,
        "topics": {"order": "order_events", "review": "review_created"},
        "shards": sorted(shards, key=lambda n: -n["events"]),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    logger.success("샤드 {}개 + manifest.json → {}", len(shards), out_dir)
    return manifest
