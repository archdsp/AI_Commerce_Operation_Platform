"""prepare 모듈 — 슬러그/결정론 event_id/벡터파싱/분할 로직."""
import json

import pandas as pd

from edge_simulator import prepare


def test_slug():
    assert prepare.slug("São Paulo") == "s_o_paulo"
    assert prepare.slug("sp__sao paulo") == "sp_sao_paulo"
    assert prepare.slug("!!!") == "na"


def test_event_id_deterministic():
    a = prepare.event_id("order_item", "o1:1")
    b = prepare.event_id("order_item", "o1:1")
    c = prepare.event_id("order_item", "o1:2")
    assert a == b          # 같은 입력 → 동일 id (재현)
    assert a != c          # 다른 입력 → 다른 id
    assert len(a) == 36    # uuid 형식


def test_vec_ts_handles_bad_values():
    out = prepare.vec_ts(pd.Series(["2018-01-10 10:00:00", "", "not-a-date"]))
    assert out.iloc[0] == pd.Timestamp("2018-01-10 10:00:00", tz="UTC")
    assert out.iloc[1] == pd.Timestamp("2017-01-01", tz="UTC")   # NaT → 기본값
    assert out.iloc[2] == pd.Timestamp("2017-01-01", tz="UTC")


def test_build_state_city(olist_dir):
    node_rows, by_type, max_ts = prepare.build(olist_dir, "state_city", "all")
    assert set(node_rows) == {"SP|sao paulo", "SP|campinas"}
    assert by_type == {"order_item": 3, "review_created": 2}   # rev1 중복 제거됨
    assert max_ts == pd.Timestamp("2018-02-25", tz="UTC")
    assert len(node_rows["SP|sao paulo"]) == 3                 # sellerA: 2 items + 1 review


def test_build_seller_granularity(olist_dir):
    node_rows, by_type, _ = prepare.build(olist_dir, "seller", "all")
    assert set(node_rows) == {"sellerA", "sellerB"}
    assert by_type == {"order_item": 3, "review_created": 2}


def test_build_events_filter(olist_dir):
    _, by_type, _ = prepare.build(olist_dir, "state_city", "reviews")
    assert by_type == {"review_created": 2}
    assert "order_item" not in by_type


def test_write_shards_deterministic(olist_dir, tmp_path):
    node_rows, by_type, max_ts = prepare.build(olist_dir, "state_city", "all")
    out = tmp_path / "edges"
    sim_today = pd.Timestamp("2026-05-31", tz="UTC")
    manifest = prepare.write_shards(node_rows, by_type, max_ts, out, sim_today, "state_city", "all")

    assert manifest["nodes"] == 2
    assert manifest["total_events"] == 5
    assert manifest["sim_today"] == "2026-05-31"
    files = sorted(out.glob("*.jsonl"))
    assert len(files) == 2

    rows = [json.loads(line) for f in files for line in f.read_text().splitlines()]
    # event_id 결정론 — prepare.event_id와 일치
    oi = next(r for r in rows if r["value"]["event_type"] == "order_item")
    nat = f"{oi['value']['payload']['order_id']}:{oi['value']['payload']['order_item_id']}"
    assert oi["value"]["event_id"] == prepare.event_id("order_item", nat)
    # occurred_at = ts + shift (shift_days 적용)
    shift = manifest["shift_days"]
    occurred = pd.Timestamp(oi["value"]["occurred_at"])
    orig = pd.Timestamp(oi["ts"])
    assert (occurred - orig).days == shift
    # 리뷰는 sim_review_date 포함
    rv = next(r for r in rows if r["value"]["event_type"] == "review_created")
    assert "sim_review_date" in rv["value"]["payload"]
