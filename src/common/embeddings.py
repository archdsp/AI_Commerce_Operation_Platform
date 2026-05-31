"""로컬 텍스트 임베딩 (fastembed, paraphrase-multilingual-MiniLM-L12-v2, 384-dim).

배치 경로(scripts/embed_reviews.py·dags/reviews_embedding_dag.py)와 **동일 모델·차원**을 사용해
같은 Qdrant `reviews` 컬렉션(size=384, Cosine)에서 적재·질의 일관성을 보장한다.
다국어 모델 — 포르투갈어 리뷰에 적합. vLLM 임베딩 불가/외부의존 회피로 로컬 ONNX(fastembed).
"""
from __future__ import annotations

from functools import lru_cache

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBED_DIM = 384


@lru_cache(maxsize=1)
def _model():
    from fastembed import TextEmbedding
    return TextEmbedding(MODEL_NAME)


def embed(texts: list[str]) -> list[list[float]]:
    """문자열 리스트 → 384-d 벡터 리스트."""
    return [list(map(float, v)) for v in _model().embed(list(texts))]
