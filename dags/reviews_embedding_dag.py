"""리뷰 텍스트 임베딩 배치 DAG — AWS MWAA (Airflow 3.2.1).

RDS `olist_raw.reviews`(코멘트 본문) → fastembed(다국어 MiniLM, 384d) → 셀프호스트 Qdrant 적재.

설계:
- 무거운 import(pymysql/fastembed/qdrant_client)는 **태스크 내부**에서 → DAG 파싱은 의존성 없이 빠르게.
- 시크릿/설정은 **Airflow Variable**: MYSQL_HOST/MYSQL_PORT/MYSQL_USER/MYSQL_PASSWORD/MYSQL_DB_OLIST,
  QDRANT_URL, QDRANT_API_KEY. (운영은 Secrets Manager 백엔드로 승격)
- 멱등: point id = uuid5(review_id) → 재실행·백필 안전.
"""
from __future__ import annotations

import pendulum
from airflow.sdk import dag, task

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
VECTOR_DIM = 384
COLLECTION = "reviews"
NS_HEX = "7b3e6a52-2f7a-4c9b-9b1e-2a1d3c4f5e6a"   # review_id → 결정론적 point id


@dag(
    dag_id="reviews_embedding",
    schedule="@daily",
    start_date=pendulum.datetime(2026, 5, 1, tz="UTC"),
    catchup=False,
    tags=["rag", "commerce", "embedding"],
    doc_md=__doc__,
)
def reviews_embedding():

    @task
    def embed_reviews(limit: int = 500) -> dict:
        import logging
        import uuid

        from airflow.sdk import Variable

        log = logging.getLogger("airflow.task")
        ns = uuid.UUID(NS_HEX)

        host = Variable.get("MYSQL_HOST")
        port = int(Variable.get("MYSQL_PORT", default="3306"))
        user = Variable.get("MYSQL_USER")
        pw = Variable.get("MYSQL_PASSWORD")
        db = Variable.get("MYSQL_DB_OLIST", default="olist_raw")
        qurl = Variable.get("QDRANT_URL")
        qkey = Variable.get("QDRANT_API_KEY", default=None)

        # ① RDS에서 코멘트 있는 리뷰
        import pymysql
        con = pymysql.connect(host=host, port=port, user=user, password=pw, database=db,
                              cursorclass=pymysql.cursors.DictCursor, connect_timeout=15)
        try:
            with con.cursor() as cur:
                cur.execute(
                    "SELECT review_id, order_id, review_score, "
                    "       review_comment_title, review_comment_message "
                    "FROM reviews "
                    "WHERE review_comment_message IS NOT NULL AND review_comment_message <> '' "
                    "ORDER BY review_id LIMIT %s", (limit,))
                rows = list(cur.fetchall())
        finally:
            con.close()
        log.info("RDS에서 코멘트 리뷰 %d건 조회", len(rows))
        if not rows:
            return {"fetched": 0, "upserted": 0}

        def text(r):
            t = (r.get("review_comment_title") or "").strip()
            m = (r.get("review_comment_message") or "").strip()
            return f"{t}. {m}" if t else m

        texts = [text(r) for r in rows]

        # ② 임베딩 (워커에서 모델 로드)
        from fastembed import TextEmbedding
        vecs = list(TextEmbedding(model_name=MODEL_NAME).embed(texts))

        # ③ Qdrant UPSERT (멱등)
        from qdrant_client import QdrantClient, models
        client = QdrantClient(url=qurl, api_key=qkey, timeout=60)
        if not client.collection_exists(COLLECTION):
            client.create_collection(
                collection_name=COLLECTION,
                vectors_config=models.VectorParams(size=VECTOR_DIM, distance=models.Distance.COSINE))
        points = [
            models.PointStruct(
                id=str(uuid.uuid5(ns, r["review_id"])), vector=v.tolist(),
                payload={"review_id": r["review_id"], "order_id": r["order_id"],
                         "score": r["review_score"], "text": text(r)})
            for r, v in zip(rows, vecs)]
        client.upsert(collection_name=COLLECTION, points=points)
        total = client.count(COLLECTION).count
        log.info("Qdrant 적재 완료: +%d (컬렉션 총 %d)", len(points), total)
        return {"fetched": len(rows), "upserted": len(points), "collection_total": total}

    embed_reviews()


reviews_embedding()
