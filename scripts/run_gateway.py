"""FastAPI 게이트웨이 로컬 기동 — .env를 안전하게 로드(셸 미경유)하고 uvicorn 실행.

AWS API Gateway가 이 백엔드(이 EC2 public:8000)로 프록시한다.
  python scripts/run_gateway.py        # 0.0.0.0:8000
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# 특수문자 많은 .env를 bash source 없이 직접 파싱(셸 해석 회피)
for _line in (ROOT / ".env").read_text().splitlines():
    _line = _line.strip()
    if _line and not _line.startswith("#") and "=" in _line:
        _k, _v = _line.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip())

sys.path.insert(0, str(ROOT / "src"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("gateway.app:app", host="0.0.0.0", port=8000, log_level="info")
