"""shards 모듈 — 샤드 로딩/필터/분배."""
import json

import pytest

from edge_simulator.shards import load_records


def _write(d, name, recs):
    (d / f"{name}.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")


def test_load_records_basic(tmp_path):
    d = tmp_path / "edges"
    d.mkdir()
    _write(d, "n1", [
        {"key": "s1", "kind": "order", "ts": "2018-01-10T10:00:00+00:00", "value": {"event_type": "order_item"}},
        {"key": "s1", "kind": "review", "ts": "2018-01-20T00:00:00+00:00", "value": {"event_type": "review_created"}},
    ])
    _write(d, "n2", [
        {"key": "s2", "kind": "order", "ts": "2018-02-01T10:00:00+00:00", "value": {"event_type": "order_item"}},
    ])
    nodes = load_records(d, 0, 1, "all")
    assert {n for n, _ in nodes} == {"n1", "n2"}
    recs = dict(nodes)["n1"]
    assert recs[0]["_ts"].year == 2018          # ts 파싱됨
    assert recs[0]["_ts"] <= recs[1]["_ts"]     # 정렬됨


def test_load_records_events_filter(tmp_path):
    d = tmp_path / "edges"
    d.mkdir()
    _write(d, "n1", [
        {"key": "s1", "kind": "order", "ts": "2018-01-10T10:00:00+00:00", "value": {}},
        {"key": "s1", "kind": "review", "ts": "2018-01-20T00:00:00+00:00", "value": {}},
    ])
    recs = load_records(d, 0, 1, "reviews")[0][1]
    assert len(recs) == 1 and all(r["kind"] == "review" for r in recs)


def test_load_records_sharding_disjoint(tmp_path):
    d = tmp_path / "edges"
    d.mkdir()
    for i in range(4):
        _write(d, f"n{i}", [{"key": f"s{i}", "kind": "order", "ts": "2018-01-10T10:00:00+00:00", "value": {}}])
    s0 = {n for n, _ in load_records(d, 0, 2, "all")}
    s1 = {n for n, _ in load_records(d, 1, 2, "all")}
    assert len(s0) == 2 and len(s1) == 2
    assert s0.isdisjoint(s1)            # 샤드가 프로듀서 간 겹치지 않음
    assert s0 | s1 == {"n0", "n1", "n2", "n3"}


def test_load_records_missing_dir(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_records(tmp_path / "nope", 0, 1, "all")
