#!/usr/bin/env python3
"""Qdrant `reviews` 재적재 — 컬렉션 재생성 후 RDS 리뷰를 통일 모델(다국어 384d)로 임베딩·적재.

혼재 벡터(초기 영어모델 + 다국어) 정리용. 배치 경로(dags/reviews_embedding_dag.py)와 동일
모델·네임스페이스(7b3e). 멱등 point id = uuid5(NS, review_id).
  python scripts/reload_qdrant.py --limit 6000
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from common.db import OLIST_DB, mysql_conn
from common.embeddings import EMBED_DIM, embed
from edge_simulator.logging_setup import setup_logging

logger = setup_logging("reload_qdrant")
NS = uuid.UUID("7b3e6a52-2f7a-4c9b-9b1e-2a1d3c4f5e6a")
COLLECTION = os.environ.get("QDRANT_COLLECTION", "reviews")


def _qclient():
    from qdrant_client import QdrantClient
    return QdrantClient(url=os.environ.get("QDRANT_URL", "http://localhost:6333"),
                        api_key=os.environ.get("QDRANT_API_KEY") or None, timeout=60)


def main() -> None:
    ap = argparse.ArgumentParser(description="Qdrant reviews 재적재")
    ap.add_argument("--limit", type=int, default=6000)
    ap.add_argument("--batch", type=int, default=256)
    args = ap.parse_args()

    from qdrant_client.models import Distance, PointStruct, VectorParams

    qc = _qclient()
    if qc.collection_exists(COLLECTION):
        qc.delete_collection(COLLECTION)
        logger.info("기존 컬렉션 삭제: {}", COLLECTION)
    qc.create_collection(COLLECTION, vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE))
    logger.info("컬렉션 재생성: {} (dim={}, Cosine)", COLLECTION, EMBED_DIM)

    con = mysql_conn(database=OLIST_DB)
    with con.cursor() as cur:
        cur.execute(
            "SELECT review_id, order_id, review_score, review_comment_title, review_comment_message "
            "FROM reviews WHERE review_comment_message IS NOT NULL AND review_comment_message <> '' "
            "ORDER BY review_id LIMIT %s", (args.limit,))
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    con.close()
    logger.info("RDS 코멘트 리뷰 {:,}건 로드", len(rows))

    total = 0
    for i in range(0, len(rows), args.batch):
        chunk = rows[i:i + args.batch]
        texts = [" ".join(x for x in (r.get("review_comment_title"), r.get("review_comment_message")) if x).strip()
                 for r in chunk]
        vecs = embed(texts)
        points = [PointStruct(id=str(uuid.uuid5(NS, r["review_id"])), vector=v,
                              payload={"review_id": r["review_id"], "order_id": r["order_id"],
                                       "score": r["review_score"], "text": t})
                  for r, t, v in zip(chunk, texts, vecs)]
        qc.upsert(COLLECTION, points=points)
        total += len(points)
        if (i // args.batch) % 5 == 0:
            logger.info("  적재 {:,}/{:,}", total, len(rows))

    logger.success("재적재 완료 | upserted={:,} | 컬렉션 points={:,}", total, qc.count(COLLECTION).count)


if __name__ == "__main__":
    main()
