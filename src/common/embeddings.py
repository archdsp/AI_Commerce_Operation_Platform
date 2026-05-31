"""로컬 텍스트 임베딩 (fastembed, all-MiniLM-L6-v2, 384-dim).

Qdrant `reviews` 컬렉션(size=384, Cosine)과 동일 모델 — 적재·질의(RAG)에 같은 모델을 써야
검색 일관성이 보장된다. vLLM 임베딩 불가/외부의존 회피를 위해 로컬 ONNX(fastembed) 사용.
"""
from __future__ import annotations

from functools import lru_cache

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384


@lru_cache(maxsize=1)
def _model():
    from fastembed import TextEmbedding
    return TextEmbedding(MODEL_NAME)


def embed(texts: list[str]) -> list[list[float]]:
    """문자열 리스트 → 384-d 벡터 리스트."""
    return [list(map(float, v)) for v in _model().embed(list(texts))]
