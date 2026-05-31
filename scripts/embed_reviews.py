"""리뷰 텍스트 임베딩 → Qdrant 적재 + 의미검색 데모 (RAG의 '적재' 절반).

흐름: RDS MySQL `olist_raw.reviews`(코멘트 본문) → fastembed(다국어, CPU) → Qdrant 컬렉션.
- 임베딩 모델: paraphrase-multilingual-MiniLM-L12-v2 (384d, 다국어, prefix 불필요)
- Qdrant: 임베디드 로컬 모드(파일 기반, 서버/Docker 불필요) — 같은 코드가 나중에 실서버로 승격
- 멱등: point id = uuid5(review_id) → 재실행해도 중복 없이 덮어씀

사용:
  python scripts/embed_reviews.py --limit 300            # 샘플 적재 + 데모 검색
  python scripts/embed_reviews.py --search "배송 지연"    # 적재된 컬렉션에 질의만
"""
from __future__ import annotations

import argparse
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
QDRANT_PATH = ROOT / ".qdrant_local"          # 생성물(.gitignore 처리)
COLLECTION = "reviews"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
VECTOR_DIM = 384
NS = uuid.UUID("7b3e6a52-2f7a-4c9b-9b1e-2a1d3c4f5e6a")  # review_id → 결정론적 point id


def load_env(path: Path) -> dict:
    """비밀번호에 특수문자가 많아 셸 노출 금지 → .env를 직접 파싱."""
    env = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def fetch_reviews(env: dict, limit: int) -> list[dict]:
    import pymysql
    con = pymysql.connect(
        host=env["MYSQL_HOST"], port=int(env.get("MYSQL_PORT", "3306")),
        user=env["MYSQL_USER"], password=env["MYSQL_PASSWORD"],
        database=env.get("MYSQL_DB_OLIST", "olist_raw"),
        cursorclass=pymysql.cursors.DictCursor, connect_timeout=10)
    try:
        with con.cursor() as cur:
            cur.execute(
                "SELECT review_id, order_id, review_score, "
                "       review_comment_title, review_comment_message "
                "FROM reviews "
                "WHERE review_comment_message IS NOT NULL AND review_comment_message <> '' "
                "ORDER BY review_id LIMIT %s", (limit,))
            return list(cur.fetchall())
    finally:
        con.close()


def review_text(r: dict) -> str:
    title = (r.get("review_comment_title") or "").strip()
    msg = (r.get("review_comment_message") or "").strip()
    return f"{title}. {msg}" if title else msg


def make_client(env: dict):
    """QDRANT_URL이 있으면 서버 모드(셀프호스트), 없으면 임베디드(로컬 파일) 폴백."""
    from qdrant_client import QdrantClient
    url = env.get("QDRANT_URL")
    if url:
        return QdrantClient(url=url, api_key=env.get("QDRANT_API_KEY"), timeout=30)
    return QdrantClient(path=str(QDRANT_PATH))


def open_collection(env: dict):
    from qdrant_client import models
    client = make_client(env)
    if not client.collection_exists(COLLECTION):
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=models.VectorParams(size=VECTOR_DIM, distance=models.Distance.COSINE))
    return client, models


def embed_and_load(env: dict, limit: int):
    from fastembed import TextEmbedding

    print(f"① RDS에서 코멘트 있는 리뷰 {limit}건 조회 ...")
    rows = fetch_reviews(env, limit)
    if not rows:
        raise SystemExit("조회 결과 0건 — 데이터/연결 확인 필요")
    texts = [review_text(r) for r in rows]
    print(f"   가져옴 {len(rows)}건 | 예시: {texts[0][:60]!r}")

    print(f"② 임베딩 인코딩 ({MODEL_NAME}, CPU) — 첫 실행은 모델 다운로드(~0.22GB) ...")
    model = TextEmbedding(model_name=MODEL_NAME)
    vectors = list(model.embed(texts))
    print(f"   벡터 {len(vectors)}개 · 차원 {len(vectors[0])}")

    print("③ Qdrant 컬렉션에 UPSERT(멱등) ...")
    client, models = open_collection(env)
    points = [
        models.PointStruct(
            id=str(uuid.uuid5(NS, r["review_id"])),
            vector=vec.tolist(),
            payload={"review_id": r["review_id"], "order_id": r["order_id"],
                     "score": r["review_score"], "text": review_text(r)})
        for r, vec in zip(rows, vectors)]
    client.upsert(collection_name=COLLECTION, points=points)
    print(f"   컬렉션 '{COLLECTION}' 포인트 수: {client.count(COLLECTION).count}")
    return model, client


def search(model, client, query: str, k: int = 5) -> None:
    qvec = next(iter(model.embed([query]))).tolist()
    res = client.query_points(collection_name=COLLECTION, query=qvec, limit=k, with_payload=True)
    print(f"\n🔎 질의: {query!r}")
    for h in res.points:
        p = h.payload
        snippet = p["text"][:80] + ("…" if len(p["text"]) > 80 else "")
        print(f"   [{h.score:.3f}] (★{p['score']}) {snippet}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=300, help="적재할 리뷰 수")
    ap.add_argument("--search", default=None, help="적재 없이 질의만 실행")
    args = ap.parse_args()
    env = load_env(ENV_PATH)

    if args.search:
        from fastembed import TextEmbedding
        model = TextEmbedding(model_name=MODEL_NAME)
        client = make_client(env)
        search(model, client, args.search)
        return

    model, client = embed_and_load(env, args.limit)
    # 데모: 포르투갈어 2건 + 한국어 1건(다국어 교차검색 확인)
    for q in ["produto veio quebrado e com defeito",       # 불량/파손되어 왔다
              "a entrega atrasou muito, demorou demais",    # 배송이 많이 늦었다
              "배송이 너무 늦게 도착했어요"]:                  # KR 질의 → PT 리뷰 검색
        search(model, client, q)


if __name__ == "__main__":
    main()
