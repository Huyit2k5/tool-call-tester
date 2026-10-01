"""OpenAI -> trace.

Nhận hai dạng:
- Chat Completions: list messages; assistant có `tool_calls`, kết quả ở message role="tool".
- Responses API: list item `function_call` / `function_call_output`.
Cũng nhận dict {"messages": [...]} hoặc {"output": [...]}.
Token: lấy `usage.total_tokens` của message assistant, gán cho lời gọi đầu tiên của nó.
"""

from __future__ import annotations

import json
from typing import Any

from ..trace import Event, Trace


def _args(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        val = json.loads(raw)
    except (TypeError, ValueError):
        return {"_raw": raw}
    return val if isinstance(val, dict) else {"_value": val}


def _maybe_json(content: Any) -> Any:
    if isinstance(content, str):
        try:
            return json.loads(content)
        except ValueError:
            return content
    return content


def to_trace(data: Any) -> Trace:
    if isinstance(data, dict):
        data = data.get("messages") or data.get("output") or data.get("input") or []
    events, by_id = [], {}

    def add(call_id, name, raw_args, tokens=0):
        e = Event(step=len(events) + 1, tool=name, args=_args(raw_args), tokens=tokens)
        events.append(e)
        if call_id:
            by_id[call_id] = e

    def finish(call_id, content):
        e = by_id.get(call_id)
        if e is None:
            return
        val = _maybe_json(content)
        if isinstance(val, dict) and val.get("error") and len(val) == 1:
            e.error = str(val["error"])
        else:
            e.result = val

    for m in data:
        t = m.get("type")
        if t == "function_call":
            add(m.get("call_id") or m.get("id"), m.get("name", ""), m.get("arguments"))
        elif t == "function_call_output":
            finish(m.get("call_id"), m.get("output"))
        elif m.get("role") == "assistant" and m.get("tool_calls"):
            tokens = (m.get("usage") or {}).get("total_tokens", 0)
            for i, tc in enumerate(m["tool_calls"]):
                fn = tc.get("function", {})
                add(tc.get("id"), fn.get("name", ""), fn.get("arguments"), tokens if i == 0 else 0)
        elif m.get("role") == "tool":
            finish(m.get("tool_call_id"), m.get("content"))
    last = data[-1] if data else {}
    final = last.get("content") if last.get("role") == "assistant" and not last.get("tool_calls") else None
    return Trace(events, final if isinstance(final, str) and final.strip() else None)
