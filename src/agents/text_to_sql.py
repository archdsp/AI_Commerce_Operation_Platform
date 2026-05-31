"""Text-to-SQL — vLLM로 MySQL SELECT 생성 → 가드레일 → 실행 (1회 self-correction)."""
from __future__ import annotations

from loguru import logger

from common.db import mysql_conn
from common.llm import chat_json

from .prompts import SCHEMA_SNIPPET, TEXT2SQL_SYS
from .sql_guard import SQLRejected, guard


def _generate(question: str, sim_today: str, fix_hint: str = "") -> str:
    user = f"SCHEMA:\n{SCHEMA_SNIPPET}\nSIM_TODAY={sim_today}\n질문: {question}"
    if fix_hint:
        user += f"\n\n이전 SQL이 다음 오류로 실패했다. 고쳐서 다시 생성하라: {fix_hint}"
    data = chat_json([{"role": "system", "content": TEXT2SQL_SYS},
                      {"role": "user", "content": user}], max_tokens=300)
    return (data.get("sql") or "").strip()


def run_sql(question: str, sim_today: str = "2026-05-31", max_rows: int = 50):
    """질문 → (안전 SQL, rows). 실행 오류 시 1회 self-correction 재시도. 실패 시 SQLRejected."""
    last_err = ""
    for attempt in range(2):
        raw = _generate(question, sim_today, last_err)
        if not raw:
            raise SQLRejected("SQL 생성 실패")
        safe = guard(raw, max_rows)            # 정책 위반 시 SQLRejected (즉시 중단)
        con = mysql_conn()
        try:
            with con.cursor() as cur:
                cur.execute(safe)
                cols = [d[0] for d in cur.description]
                rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            return safe, rows
        except Exception as exc:  # noqa: BLE001  (실행 오류 → self-correct)
            last_err = str(exc)[:200]
            logger.warning("SQL 실행 실패(시도 {}): {}", attempt + 1, last_err)
        finally:
            con.close()
    raise SQLRejected(f"SQL 실행 실패: {last_err}")
