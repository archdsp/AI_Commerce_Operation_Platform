"""FastAPI Gateway 백엔드 — 에이전트 실행/노출. AWS API Gateway(프론트)가 이 앞에서
인증·throttle·라우팅을 관리형으로 처리하고, 통과한 요청을 여기로 프록시한다.

엔드포인트: /v1/{chat, agent/run, sql/generate, usage, models}, /health.
인증: X-API-Key(sha256 → commerce_ops.api_keys). 로깅: agent_requests/executions/model_usage_logs.
"""
from __future__ import annotations

import hashlib
import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel

from agents.graph import answer_query
from agents.sql_guard import SQLRejected
from agents.text_to_sql import run_sql
from common.db import OPS_DB, mysql_conn
from common.llm import DEFAULT_MODEL
from edge_simulator.logging_setup import setup_logging

setup_logging("gateway")
app = FastAPI(title="AI Commerce Ops Gateway", version="0.1.0")

# AWS API Gateway 우회 직접호출 차단: GATEWAY_ORIGIN_SECRET 설정 시 /v1/* 는
# API Gateway가 주입하는 X-Origin-Secret 헤더가 일치해야 통과한다(미설정이면 로컬 개발용으로 검증 생략).
ORIGIN_SECRET = os.environ.get("GATEWAY_ORIGIN_SECRET")


@app.middleware("http")
async def verify_origin(request: Request, call_next):
    if ORIGIN_SECRET and request.url.path.startswith("/v1"):
        if request.headers.get("X-Origin-Secret") != ORIGIN_SECRET:
            return JSONResponse(status_code=403, content={"detail": "직접 접근 불가 — API Gateway 경유 필요"})
    return await call_next(request)


class ChatReq(BaseModel):
    query: str
    session_id: str | None = None


class AgentRunReq(BaseModel):
    agent_type: str
    query: str


class SqlReq(BaseModel):
    query: str


def require_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key 헤더 필요")
    h = hashlib.sha256(x_api_key.encode()).hexdigest()
    con = mysql_conn(database=OPS_DB)
    try:
        with con.cursor() as cur:
            cur.execute("SELECT id FROM api_keys WHERE key_hash=%s AND is_active=1", (h,))
            row = cur.fetchone()
    finally:
        con.close()
    if not row:
        raise HTTPException(status_code=401, detail="유효하지 않은 API Key")
    return row[0]


def _log(api_key_id, endpoint, query, agent_type, latency_ms, sql=None, rows=0, status="success"):
    rid = str(uuid.uuid4())
    con = mysql_conn(database=OPS_DB)
    try:
        with con.cursor() as cur:
            cur.execute("INSERT INTO agent_requests(id,api_key_id,endpoint,query_text,agent_type,latency_ms) "
                        "VALUES(%s,%s,%s,%s,%s,%s)", (rid, api_key_id, endpoint, query, agent_type, latency_ms))
            cur.execute("INSERT INTO agent_executions(request_id,status,generated_sql,rows_returned,latency_ms) "
                        "VALUES(%s,%s,%s,%s,%s)", (rid, status, sql, rows, latency_ms))
            cur.execute("INSERT INTO model_usage_logs(request_id,provider,model) VALUES(%s,%s,%s)",
                        (rid, "runpod", DEFAULT_MODEL))
        con.commit()
    except Exception as exc:  # noqa: BLE001
        con.rollback()
        logger.warning("로깅 실패: {}", exc)
    finally:
        con.close()
    return rid


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/v1/models")
def models(_: str = Depends(require_key)):
    return {"data": [{"id": DEFAULT_MODEL, "provider": "runpod"}]}


@app.post("/v1/chat")
def chat(req: ChatReq, key_id: str = Depends(require_key)):
    t = time.time()
    r = answer_query(req.query)
    ms = int((time.time() - t) * 1000)
    _log(key_id, "/v1/chat", req.query, r.get("agent_type"), ms, r.get("sql"), len(r.get("rows", [])))
    return {"agent_type": r.get("agent_type"), "answer": r.get("answer"), "sql": r.get("sql"),
            "rows_count": len(r.get("rows", [])), "model": DEFAULT_MODEL, "latency_ms": ms}


@app.post("/v1/agent/run")
def agent_run(req: AgentRunReq, key_id: str = Depends(require_key)):
    if req.agent_type not in ("md", "voc", "insight"):
        raise HTTPException(status_code=400, detail="agent_type은 md/voc/insight")
    t = time.time()
    r = answer_query(req.query, req.agent_type)
    ms = int((time.time() - t) * 1000)
    _log(key_id, "/v1/agent/run", req.query, req.agent_type, ms, r.get("sql"), len(r.get("rows", [])))
    return {"agent_type": req.agent_type, "answer": r.get("answer"), "sql": r.get("sql"),
            "rows_count": len(r.get("rows", [])), "latency_ms": ms}


@app.post("/v1/sql/generate")
def sql_generate(req: SqlReq, key_id: str = Depends(require_key)):
    t = time.time()
    try:
        sql, rows = run_sql(req.query)
    except SQLRejected as exc:
        _log(key_id, "/v1/sql/generate", req.query, "text2sql", int((time.time() - t) * 1000), status="sql_rejected")
        raise HTTPException(status_code=400, detail=f"SQL 거부/실패: {exc}")
    ms = int((time.time() - t) * 1000)
    _log(key_id, "/v1/sql/generate", req.query, "text2sql", ms, sql, len(rows))
    return {"sql": sql, "rows": rows[:50], "rows_count": len(rows), "latency_ms": ms}


@app.get("/v1/usage")
def usage(_: str = Depends(require_key)):
    con = mysql_conn(database=OPS_DB)
    try:
        with con.cursor() as cur:
            cur.execute("SELECT COUNT(*), AVG(latency_ms) FROM agent_requests")
            total, avg = cur.fetchone()
            cur.execute("SELECT endpoint, COUNT(*) FROM agent_requests GROUP BY endpoint")
            by_ep = dict(cur.fetchall())
            cur.execute("SELECT COUNT(*) FROM model_usage_logs")
            calls = cur.fetchone()[0]
    finally:
        con.close()
    return {"total_requests": total or 0, "avg_latency_ms": round(float(avg), 1) if avg else 0,
            "by_endpoint": by_ep, "model_calls": calls}
