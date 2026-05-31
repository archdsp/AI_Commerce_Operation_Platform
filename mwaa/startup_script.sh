#!/bin/sh
# MWAA 시작 스크립트 — 워커/스케줄러/웹서버 부팅 시 실행.
# requirements.txt가 워커에 설치되지 않는 문제(Airflow 3.2.1 env)를 우회해
# daily_commerce_ops_pipeline DAG가 쓰는 pymysql을 강제 설치한다.
# (startup script는 requirements.txt와 다른 메커니즘이라 더 확실히 적용된다.)
echo "[startup_script] installing pymysql for daily_commerce_ops_pipeline DAG"
pip install pymysql==1.2.0
