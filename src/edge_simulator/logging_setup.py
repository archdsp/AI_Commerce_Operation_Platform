"""loguru 기반 로깅 설정.

로그는 기본적으로 ``/workspace/app_logs/{app_name}/`` 아래에 남는다 (환경변수 APP_LOG_DIR로 변경 가능).
콘솔(stderr)에도 동시 출력한다. 각 엔트리포인트는 시작 시 ``setup_logging("edge_simulator")`` 를 호출한다.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from loguru import logger

DEFAULT_LOG_BASE = "/workspace/app_logs"

_CONSOLE_FMT = "<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | <cyan>{name}</cyan> - {message}"
_FILE_FMT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <7} | {name}:{function}:{line} - {message}"


def setup_logging(app_name: str, level: str | None = None):
    """loguru 핸들러를 (재)설정하고 logger를 반환.

    파일 sink: {APP_LOG_DIR}/{app_name}/{app_name}_{date}.log (50MB 회전, 7일 보관).
    디렉터리 생성 실패 시 콘솔 로깅만 유지한다.
    """
    level = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()
    base = os.environ.get("APP_LOG_DIR", DEFAULT_LOG_BASE)

    logger.remove()
    logger.add(sys.stderr, level=level, format=_CONSOLE_FMT, enqueue=True)

    log_dir = Path(base) / app_name
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_dir / f"{app_name}_{{time:YYYY-MM-DD}}.log",
            level=level,
            rotation="50 MB",
            retention="7 days",
            encoding="utf-8",
            enqueue=True,
            backtrace=True,
            diagnose=False,
            format=_FILE_FMT,
        )
        logger.debug("파일 로그 → {}", log_dir)
    except OSError as exc:
        logger.warning("로그 디렉터리 생성 실패 ({}): {} — 콘솔만 사용", log_dir, exc)

    return logger
