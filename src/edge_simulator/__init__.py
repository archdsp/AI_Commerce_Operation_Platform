"""Olist 엣지 점포 시뮬레이터 (모듈 패키지).

이 패키지에는 **구성요소(모듈)** 만 둔다. 실행 가능한 CLI 엔트리포인트는 `scripts/` 에 있다:
  scripts/prepare_edges.py  → edge_simulator.prepare   (CSV → 점포별 샤드)
  scripts/run.py            → edge_simulator.producer  (샤드 → MSK 발행)
  scripts/kafka_admin.py    → edge_simulator.admin     (토픽 생성/리셋/목록)
  scripts/consume_check.py  → edge_simulator.verify    (도착 검증)
"""

__version__ = "0.1.0"
