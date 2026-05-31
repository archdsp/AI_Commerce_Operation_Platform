"""LangGraph 멀티에이전트 그래프 — route → retrieve(Text-to-SQL + RAG) → synthesize(vLLM).

docs/AGENTS.md §2/§8. 라우팅: 규칙(VOC>Insight>MD) 우선, 명시 agent_type이면 그대로.
"""
from __future__ import annotations

import json
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from loguru import logger

from common.llm import chat

from .prompts import SYSTEM
from .rag import search_reviews
from .sql_guard import SQLRejected
from .text_to_sql import run_sql

VOC_KW = ["리뷰", "voc", "불만", "배송", "품질", "감성", "부정", "후기", "평점", "고객"]
INS_KW = ["원인", "kpi", "이탈", "리포트", "요약", "전략", "전월", "추이", "액션", "분석해"]


class AgentState(TypedDict, total=False):
    query: str
    agent_type: str
    sim_today: str
    sql: str
    rows: list
    rag: list
    answer: str
    note: str


def route(state: AgentState) -> dict:
    if state.get("agent_type") in ("md", "voc", "insight"):
        return {"agent_type": state["agent_type"]}
    q = state["query"].lower()
    agent = "voc" if any(k in q for k in VOC_KW) else "insight" if any(k in q for k in INS_KW) else "md"
    logger.info("route → {}", agent)
    return {"agent_type": agent}


def retrieve(state: AgentState) -> dict:
    out: dict = {"rows": [], "rag": []}
    try:
        sql, rows = run_sql(state["query"], state.get("sim_today", "2026-05-31"))
        out["sql"], out["rows"] = sql, rows
        logger.info("SQL rows={} | {}", len(rows), sql[:120])
    except SQLRejected as exc:
        out["note"] = f"SQL 사용 불가: {exc}"
        logger.warning(out["note"])
    except Exception as exc:  # noqa: BLE001
        out["note"] = f"SQL 오류: {exc}"
        logger.warning(out["note"])
    if state.get("agent_type") == "voc":
        try:
            out["rag"] = search_reviews(state["query"], limit=5)
            logger.info("RAG hits={}", len(out["rag"]))
        except Exception as exc:  # noqa: BLE001
            logger.warning("RAG 실패: {}", exc)
    return out


def synthesize(state: AgentState) -> dict:
    rows = state.get("rows") or []
    ctx = f"[SQL 결과 {len(rows)}행]\n{json.dumps(rows[:20], ensure_ascii=False, default=str)}"
    if state.get("rag"):
        ctx += f"\n\n[관련 리뷰(RAG)]\n{json.dumps(state['rag'], ensure_ascii=False, default=str)}"
    if state.get("note"):
        ctx += f"\n\n[참고] {state['note']}"
    msgs = [{"role": "system", "content": SYSTEM.get(state.get("agent_type", "md"), SYSTEM["md"])},
            {"role": "user", "content": f"질문: {state['query']}\n\n근거 데이터:\n{ctx}\n\n위 근거만으로 한국어로 답하라."}]
    return {"answer": chat(msgs, max_tokens=600)}


_GRAPH = None


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("route", route)
    g.add_node("retrieve", retrieve)
    g.add_node("synthesize", synthesize)
    g.add_edge(START, "route")
    g.add_edge("route", "retrieve")
    g.add_edge("retrieve", "synthesize")
    g.add_edge("synthesize", END)
    return g.compile()


def answer_query(query: str, agent_type: str | None = None, sim_today: str = "2026-05-31") -> dict:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH.invoke({"query": query, "agent_type": agent_type or "", "sim_today": sim_today})
