#!/usr/bin/env python3
"""MWAA 마무리 — Airflow Variables 주입 + reviews_embedding DAG unpause/trigger.

전제: cj-airflow AVAILABLE(requirements 적용 완료), SG 6333 개방, Qdrant 가동.
.env에서 시크릿을 읽어 MWAA CLI 토큰으로 Variable을 설정한다(셸 노출 없음).
QDRANT_URL은 MWAA(다른 VPC)에서 접속할 **public IP**를 쓴다.

  python mwaa/finish_mwaa_setup.py
"""
from __future__ import annotations

import base64
import json
import subprocess
import urllib.request
from pathlib import Path

ENV = Path(__file__).resolve().parents[1] / ".env"
REGION = "ap-northeast-2"
ENVNAME = "cj-airflow"
QDRANT_PUBLIC_URL = "http://43.202.253.112:6333"   # MWAA는 vpc-0962 → public IP로 접속


def load_env(p: Path) -> dict:
    d = {}
    for line in p.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def cli_token() -> tuple[str, str]:
    out = subprocess.check_output(
        ["aws", "mwaa", "create-cli-token", "--name", ENVNAME, "--region", REGION])
    j = json.loads(out)
    return j["WebServerHostname"], j["CliToken"]


def run_cli(host: str, token: str, command: str) -> tuple[str, str]:
    req = urllib.request.Request(
        f"https://{host}/aws_mwaa/cli/", data=command.encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "text/plain"})
    with urllib.request.urlopen(req, timeout=30) as r:
        j = json.loads(r.read())
    return (base64.b64decode(j.get("stdout", "")).decode(errors="replace"),
            base64.b64decode(j.get("stderr", "")).decode(errors="replace"))


def tail(s: str) -> str:
    lines = [x for x in s.splitlines() if x.strip() and "CloudWatch logging" not in x]
    return lines[-1] if lines else "(빈 출력)"


def main() -> None:
    env = load_env(ENV)
    variables = {
        "MYSQL_HOST": env["MYSQL_HOST"],
        "MYSQL_PORT": env.get("MYSQL_PORT", "3306"),
        "MYSQL_USER": env["MYSQL_USER"],
        "MYSQL_PASSWORD": env["MYSQL_PASSWORD"],
        "MYSQL_DB_OLIST": env.get("MYSQL_DB_OLIST", "olist_raw"),
        "QDRANT_URL": QDRANT_PUBLIC_URL,
        "QDRANT_API_KEY": env.get("QDRANT_API_KEY", ""),
    }
    host, token = cli_token()
    for k, v in variables.items():
        out, err = run_cli(host, token, f"variables set {k} {v}")
        masked = v if k not in ("MYSQL_PASSWORD", "QDRANT_API_KEY") else f"<{len(v)}자>"
        print(f"  set {k}={masked} → {tail(out or err)}")

    # 비밀번호 라운드트립 검증(특수문자 안전 확인)
    out, _ = run_cli(host, token, "variables get MYSQL_PASSWORD")
    print("  MYSQL_PASSWORD 라운드트립 일치:", tail(out) == env["MYSQL_PASSWORD"])

    # 임베딩 DAG는 pause(스트리밍 컨슈머로 이관), 집계 DAG를 unpause+trigger
    for cmd in ("dags pause reviews_embedding",
                "dags unpause daily_commerce_ops_pipeline",
                "dags trigger daily_commerce_ops_pipeline"):
        out, err = run_cli(host, token, cmd)
        print(f"$ {cmd} → {tail(out or err)}")


if __name__ == "__main__":
    main()
