"""RAG 검색 — 질의 임베딩(다국어 384d) → Qdrant `reviews` 유사도 검색."""
from __future__ import annotations

import os

from common.embeddings import embed


def search_reviews(query: str, limit: int = 5) -> list[dict]:
    from qdrant_client import QdrantClient

    qc = QdrantClient(url=os.environ.get("QDRANT_URL", "http://localhost:6333"),
                      api_key=os.environ.get("QDRANT_API_KEY") or None, timeout=30)
    pts = qc.query_points(os.environ.get("QDRANT_COLLECTION", "reviews"),
                          query=embed([query])[0], limit=limit, with_payload=True).points
    return [{"review_id": p.payload.get("review_id"), "score": p.payload.get("score"),
             "sim": round(p.score, 3), "text": p.payload.get("text")} for p in pts]
