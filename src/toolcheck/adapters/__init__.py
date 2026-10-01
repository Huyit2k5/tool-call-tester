"""Adapter: chuyển log/payload của từng nền tảng về trace chuẩn.

Chỉ đọc dict/JSON thuần nên không cần cài SDK; extras trong pyproject (openai,
anthropic, mcp) dành cho người muốn kéo SDK về cùng để chạy ví dụ tích hợp.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List

from ..trace import Trace
from . import anthropic as _anthropic
from . import mcp as _mcp
from . import openai as _openai
from . import otel as _otel

ADAPTERS: Dict[str, Callable[[Any], Trace]] = {
    "openai": _openai.to_trace,
    "anthropic": _anthropic.to_trace,
    "mcp": _mcp.to_trace,
    "otel": _otel.to_trace,
}


def load_json_or_jsonl(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        out: List[Any] = []
        for n, line in enumerate(text.splitlines(), 1):
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path} dòng {n}: JSON sai ({exc.msg})") from exc
        return out


def convert(kind: str, data: Any) -> Trace:
    if kind not in ADAPTERS:
        raise ValueError(f"adapter '{kind}' không có; hợp lệ: {sorted(ADAPTERS)}")
    return ADAPTERS[kind](data)
