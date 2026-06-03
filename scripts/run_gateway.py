"""FastAPI 게이트웨이 로컬 기동 — .env를 안전하게 로드(셸 미경유)하고 uvicorn 실행.

AWS API Gateway가 이 백엔드(이 EC2 public:8000)로 프록시한다.
  python scripts/run_gateway.py        # 0.0.0.0:8000
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# 특수문자 많은 env 파일을 bash source 없이 직접 파싱(셸 해석 회피).
# ENV_FILE(예: .env.local)이 있으면 우선, 없으면 .env. 파일이 없으면 건너뜀(이미 export된 환경변수 사용 → 로컬 첫 실행에서 .env 부재 허용).
_ENV_PATH = ROOT / (os.environ.get("ENV_FILE") or ".env")
if _ENV_PATH.exists():
    for _line in _ENV_PATH.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

sys.path.insert(0, str(ROOT / "src"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("gateway.app:app", host="0.0.0.0",
                port=int(os.environ.get("GW_PORT", "8000")), log_level="info")
