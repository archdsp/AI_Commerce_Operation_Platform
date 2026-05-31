"""RunPod vLLM (OpenAI 호환) 클라이언트.

RunPod 프록시(`*.proxy.runpod.net`)는 Cloudflare 뒤에 있어, 브라우저 User-Agent가 없으면
데이터센터 IP 요청을 **error 1010**으로 차단한다 → 모든 호출에 브라우저 UA를 강제한다.
.env: VLLM_URL, VLLM_API_KEY, (선택) VLLM_MODEL.
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
DEFAULT_MODEL = os.environ.get("VLLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")


def base_url() -> str:
    raw = (os.environ.get("VLLM_URL") or os.environ.get("RUNPOD_BASE_URL") or "").rstrip("/")
    return raw if raw.endswith("/v1") else raw + "/v1"


def _headers() -> dict:
    return {
        "User-Agent": _UA,                                    # Cloudflare 1010 회피 (필수)
        "Authorization": f"Bearer {os.environ.get('VLLM_API_KEY', '')}",
        "Content-Type": "application/json",
    }


def chat(messages: list[dict], model: str | None = None, temperature: float = 0.0,
         max_tokens: int = 512, timeout: int = 60) -> str:
    """OpenAI 호환 chat completion → 응답 텍스트."""
    body = json.dumps({"model": model or DEFAULT_MODEL, "messages": messages,
                       "temperature": temperature, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(base_url() + "/chat/completions", data=body, headers=_headers())
    resp = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    return resp["choices"][0]["message"]["content"]


def chat_json(messages: list[dict], **kw) -> dict:
    """JSON 출력을 기대하는 호출 — 본문에서 첫 {…} 블록을 파싱."""
    text = chat(messages, **kw)
    s, e = text.find("{"), text.rfind("}")
    if s >= 0 and e > s:
        try:
            return json.loads(text[s:e + 1])
        except json.JSONDecodeError:
            return {}
    return {}
