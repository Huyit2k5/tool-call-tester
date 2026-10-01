"""OpenTelemetry (GenAI semantic conventions) <-> trace.

Span công cụ: tên "execute_tool <tool>", thuộc tính:
  gen_ai.tool.name, gen_ai.tool.call.arguments (JSON), gen_ai.tool.call.result,
  gen_ai.usage.input_tokens / output_tokens; lỗi qua status.code == 2 (ERROR) hoặc error.type.
Nhập: list span dạng dict phẳng; `attributes` là dict hoặc list OTLP-JSON [{key, value:{stringValue,...}}].
Xuất: to_spans(trace) trả list span dict phẳng (dùng được với bộ ghi JSON/OTLP tùy ý).
"""

from __future__ import annotations

import json
from typing import Any, List

from ..trace import Event, Trace

TOOL_NAME = "gen_ai.tool.name"
TOOL_ARGS = "gen_ai.tool.call.arguments"
TOOL_RESULT = "gen_ai.tool.call.result"
IN_TOK = "gen_ai.usage.input_tokens"
OUT_TOK = "gen_ai.usage.output_tokens"


def _attrs(span: dict) -> dict:
    a = span.get("attributes") or {}
    if isinstance(a, dict):
        return a
    out = {}
    for item in a:
        v = item.get("value", {})
        out[item["key"]] = next(iter(v.values())) if isinstance(v, dict) and v else v
    return out


def _json(v: Any) -> Any:
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return v
    return v


def to_trace(data: Any) -> Trace:
    if isinstance(data, dict):
        data = data.get("spans") or []
    items = []
    for s in data:
        a = _attrs(s)
        name = a.get(TOOL_NAME) or (s.get("name", "").split(" ", 1)[1] if s.get("name", "").startswith("execute_tool ") else None)
        if name:
            items.append((int(s.get("start_time_unix_nano") or 0), s, a, name))
    items.sort(key=lambda x: x[0])
    events = []
    for i, (start, s, a, name) in enumerate(items, 1):
        args = _json(a.get(TOOL_ARGS)) or {}
        if not isinstance(args, dict):
            args = {"_value": args}
        status = s.get("status") or {}
        failed = status.get("code") in (2, "ERROR", "STATUS_CODE_ERROR") or "error.type" in a
        err = None
        if failed:
            err = str(a.get("error.type") or status.get("message") or "error")
        events.append(Event(
            step=i, tool=name, args=args,
            result=None if failed else _json(a.get(TOOL_RESULT)), error=err,
            ts=start / 1e9 if start else None,
            tokens=int(a.get(IN_TOK, 0)) + int(a.get(OUT_TOK, 0)),
        ))
    return Trace(events)


def to_spans(trace: Trace) -> List[dict]:
    spans = []
    for e in trace.events:
        start = int((e.ts or 0) * 1e9)
        attrs = {TOOL_NAME: e.tool, TOOL_ARGS: json.dumps(e.args, ensure_ascii=False)}
        if e.result is not None:
            attrs[TOOL_RESULT] = json.dumps(e.result, ensure_ascii=False)
        if e.tokens:
            attrs[IN_TOK], attrs[OUT_TOK] = e.tokens, 0
        span = {"name": f"execute_tool {e.tool}", "start_time_unix_nano": start,
                "end_time_unix_nano": start, "attributes": attrs,
                "status": {"code": 2, "message": e.error} if e.error else {"code": 1}}
        if e.error:
            attrs["error.type"] = e.error
        spans.append(span)
    return spans
