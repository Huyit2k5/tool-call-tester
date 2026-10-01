"""MCP (JSON-RPC log) -> trace.

Nhận list message JSON-RPC (hoặc JSONL): request `tools/call` {id, params:{name, arguments}}
ghép với response cùng `id`: `result` ({content, isError, structuredContent}) hoặc `error`.
"""

from __future__ import annotations

import json
from typing import Any

from ..trace import Event, Trace


def _result_value(res: dict) -> Any:
    if "structuredContent" in res:
        return res["structuredContent"]
    content = res.get("content")
    if isinstance(content, list):
        texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
        if texts:
            joined = "\n".join(texts)
            try:
                return json.loads(joined)
            except ValueError:
                return joined
    return content


def to_trace(data: Any) -> Trace:
    if isinstance(data, dict):
        data = data.get("messages") or []
    events, by_id = [], {}
    for m in data:
        if m.get("method") == "tools/call":
            p = m.get("params") or {}
            e = Event(step=len(events) + 1, tool=p.get("name", ""), args=p.get("arguments") or {})
            events.append(e)
            by_id[m.get("id")] = e
        elif "id" in m and ("result" in m or "error" in m) and m["id"] in by_id:
            e = by_id[m["id"]]
            if "error" in m:
                err = m["error"]
                e.error = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            else:
                res = m["result"] or {}
                val = _result_value(res)
                if res.get("isError"):
                    e.error = val if isinstance(val, str) else json.dumps(val, ensure_ascii=False)
                else:
                    e.result = val
    return Trace(events)
