"""producer 모듈 — 합성복제(expand) / Pacer."""
from edge_simulator.producer import Pacer, expand


def _rec():
    return {
        "key": "s1",
        "kind": "order",
        "value": {
            "event_id": "E",
            "event_type": "order_item",
            "occurred_at": "2026-01-01T00:00:00+00:00",
            "payload": {"seller_id": "s1", "order_id": "o1", "review_id": None, "price": 1.0},
        },
    }


def test_expand_scale1_passthrough():
    out = list(expand(_rec(), 1))
    assert len(out) == 1
    key, kind, value = out[0]
    assert key == "s1" and kind == "order"
    assert value["event_id"] == "E"


def test_expand_scale2_namespacing():
    rec = _rec()
    out = list(expand(rec, 2))
    assert len(out) == 2
    (k0, _, v0), (k1, _, v1) = out
    # 0번은 원본
    assert k0 == "s1" and v0["event_id"] == "E"
    # 1번은 합성 점포 — 키·id 네임스페이스 분리
    assert k1 == "s1-r1"
    assert v1["event_id"] == "E:r1"
    assert v1["payload"]["seller_id"] == "syn1:s1"
    assert v1["payload"]["order_id"] == "syn1:o1"
    # review_id가 None이면 건드리지 않음
    assert v1["payload"]["review_id"] is None
    # 원본 payload 불변(깊은 복사)
    assert rec["value"]["payload"]["seller_id"] == "s1"


def test_pacer_interval():
    assert Pacer(1000).interval == 0.001
    assert Pacer(0).interval == 0.0
