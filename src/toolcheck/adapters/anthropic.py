"""Anthropic Messages -> trace.

Nhận list messages: assistant có block `tool_use` {id, name, input}; kết quả là block
`tool_result` {tool_use_id, content, is_error} trong message user.
Token: `usage.input_tokens + output_tokens` của message assistant, gán cho tool_use đầu tiên.
"""

from __future__ import annotations

import json
from typing import Any

from ..trace import Event, Trace


def _text(content: Any) -> Any:
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        content = "\n".join(parts) if parts else content
    if isinstance(content, str):
        try:
            return json.loads(content)
        except ValueError:
            return content
    return content


def to_trace(data: Any) -> Trace:
    if isinstance(data, dict):
        data = data.get("messages") or []
    events, by_id = [], {}
    for m in data:
        blocks = m.get("content")
        if not isinstance(blocks, list):
            continue
        usage = m.get("usage") or {}
        tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        first = True
        for b in blocks:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                e = Event(step=len(events) + 1, tool=b.get("name", ""), args=b.get("input") or {},
                          tokens=tokens if first else 0)
                first = False
                events.append(e)
                by_id[b.get("id")] = e
            elif b.get("type") == "tool_result":
                e = by_id.get(b.get("tool_use_id"))
                if e is None:
                    continue
                val = _text(b.get("content"))
                if b.get("is_error"):
                    e.error = val if isinstance(val, str) else json.dumps(val, ensure_ascii=False)
                else:
                    e.result = val
    final = None
    last = data[-1] if data else {}
    if last.get("role") == "assistant":
        c = last.get("content")
        blocks = c if isinstance(c, list) else [{"type": "text", "text": c}] if isinstance(c, str) else []
        if not any(isinstance(b, dict) and b.get("type") == "tool_use" for b in blocks):
            text = "\n".join(b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text")
            final = text.strip() or None
    return Trace(events, final)
