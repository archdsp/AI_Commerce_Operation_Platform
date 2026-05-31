"""리뷰 감성·VOC 분류.

기본은 **휴리스틱**(평점 + 포르투갈어 키워드)이라 외부 의존 없이 즉시 동작한다.
`mode="llm"`이면 RunPod(OpenAI 호환) 엔드포인트를 호출하고, 실패 시 휴리스틱으로 폴백한다.
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass

from loguru import logger

SENTIMENTS = ("positive", "neutral", "negative")
VOC_CATEGORIES = ("quality", "delivery", "price", "service", "other")

# VOC 카테고리별 포르투갈어 키워드(부분일치)
_VOC_KEYWORDS = {
    "delivery": ["entrega", "atras", "chegou", "prazo", "correio", "demor", "nao chegou", "não chegou", "envio"],
    "quality": ["qualidade", "quebrad", "defeit", "danificad", "estragad", "péssim", "pessim", "veio errad", "ruim"],
    "price": ["preço", "preco", "caro", "barato", "valor", "custo"],
    "service": ["atendimento", "vendedor", "suporte", "resposta", "contato", "reclamaç"],
}


@dataclass
class Analysis:
    sentiment: str
    voc_category: str
    confidence: float


def analyze_heuristic(review_score, title, message) -> Analysis:
    """평점으로 감성, 키워드로 VOC 카테고리 판정."""
    text = f"{title or ''} {message or ''}".lower()
    if review_score is None:
        sentiment, conf = "neutral", 0.40
    elif review_score >= 4:
        sentiment, conf = "positive", 0.90
    elif review_score == 3:
        sentiment, conf = "neutral", 0.60
    else:
        sentiment, conf = "negative", 0.90

    voc = "other"
    for category, keywords in _VOC_KEYWORDS.items():
        if any(k in text for k in keywords):
            voc = category
            break
    return Analysis(sentiment, voc, conf)


def analyze_llm(review_score, title, message) -> Analysis:
    """RunPod(OpenAI 호환) 호출. RUNPOD_BASE_URL/_MODEL/_API_KEY 사용. 미설정 시 예외."""
    base = os.environ.get("RUNPOD_BASE_URL") or os.environ.get("LLM_BASE_URL")
    if not base:
        raise RuntimeError("RUNPOD_BASE_URL 미설정")
    model = os.environ.get("RUNPOD_MODEL", "Qwen2.5-Coder-32B-Instruct")
    prompt = (
        "다음 커머스 리뷰를 분류해 JSON만 출력하라. "
        '{"sentiment":"positive|neutral|negative","voc_category":"quality|delivery|price|service|other","confidence":0~1}\n'
        f"평점: {review_score}\n제목: {title}\n내용: {message}"
    )
    payload = json.dumps({
        "model": model, "temperature": 0, "max_tokens": 120,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions", data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {os.environ.get('RUNPOD_API_KEY', '')}"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        content = json.loads(resp.read())["choices"][0]["message"]["content"]
    data = json.loads(content[content.find("{"): content.rfind("}") + 1])
    sent = data["sentiment"] if data.get("sentiment") in SENTIMENTS else "neutral"
    voc = data["voc_category"] if data.get("voc_category") in VOC_CATEGORIES else "other"
    return Analysis(sent, voc, float(data.get("confidence", 0.7)))


def analyze(review_score, title, message, mode: str = "heuristic") -> Analysis:
    if mode == "llm":
        try:
            return analyze_llm(review_score, title, message)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM 분석 실패({}) → 휴리스틱 폴백", exc)
    return analyze_heuristic(review_score, title, message)
