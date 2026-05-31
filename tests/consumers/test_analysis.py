"""Review Analyzer 분류 휴리스틱 + LLM 폴백."""
from consumers.analysis import SENTIMENTS, VOC_CATEGORIES, analyze, analyze_heuristic


def test_sentiment_from_score():
    assert analyze_heuristic(5, "", "").sentiment == "positive"
    assert analyze_heuristic(3, "", "").sentiment == "neutral"
    assert analyze_heuristic(1, "", "").sentiment == "negative"
    assert analyze_heuristic(None, "", "").sentiment == "neutral"


def test_voc_delivery():
    a = analyze_heuristic(2, "Atraso", "Produto chegou com atraso enorme")
    assert a.voc_category == "delivery"
    assert a.sentiment == "negative"


def test_voc_quality():
    assert analyze_heuristic(1, "", "veio quebrado, péssima qualidade").voc_category == "quality"


def test_voc_price():
    assert analyze_heuristic(3, "", "muito caro pelo valor").voc_category == "price"


def test_voc_other_default():
    assert analyze_heuristic(5, "Bom", "gostei do produto").voc_category == "other"


def test_outputs_in_vocab():
    a = analyze_heuristic(4, "x", "entrega rápida")
    assert a.sentiment in SENTIMENTS and a.voc_category in VOC_CATEGORIES
    assert 0.0 <= a.confidence <= 1.0


def test_analyze_llm_falls_back_without_endpoint(monkeypatch):
    # RUNPOD 미설정이면 llm 모드도 예외 없이 휴리스틱으로 폴백
    monkeypatch.delenv("RUNPOD_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    a = analyze(1, "", "produto quebrado", mode="llm")
    assert a.sentiment == "negative" and a.voc_category == "quality"
