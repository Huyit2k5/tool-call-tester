"""Tool giả, replay và chèn lỗi. Sandbox ghi lại trace chuẩn khi agent gọi tool.

    sb = Sandbox({"find": lambda args, state: {"id": 1}},
                 faults=[{"tool": "find", "on_call": 1, "kind": "error", "code": 400}])
    sb.call("find", {})   # lần 1 raise ToolError("400"), lần 2 chạy thật
    sb.trace, sb.state
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

from .trace import Event, Trace, call_hash


class ToolError(Exception):
    pass


FAULT_KINDS = {"error", "timeout", "empty"}


class Sandbox:
    def __init__(self, tools: Dict[str, Callable[[dict, dict], Any]],
                 faults: Optional[List[dict]] = None, state: Optional[dict] = None,
                 clock: Callable[[], float] = time.time):
        for f in faults or []:
            if f.get("kind") not in FAULT_KINDS:
                raise ValueError(f"fault.kind phải thuộc {sorted(FAULT_KINDS)}: {f}")
            if "tool" not in f or "on_call" not in f:
                raise ValueError(f"fault cần 'tool' và 'on_call': {f}")
        self.tools, self.faults = tools, faults or []
        self.state = state if state is not None else {}
        self.trace = Trace()
        self._counts: Dict[str, int] = defaultdict(int)
        self._clock = clock

    def _record(self, tool, args, result=None, error=None, tokens=0):
        self.trace.append(Event(step=len(self.trace) + 1, tool=tool, args=args,
                                result=result, error=error, ts=self._clock(), tokens=tokens))

    def call(self, tool: str, args: dict, tokens: int = 0):
        self._counts[tool] += 1
        n = self._counts[tool]
        fault = next((f for f in self.faults if f["tool"] == tool and f["on_call"] == n), None)
        if fault:
            kind = fault["kind"]
            if kind == "empty":
                res = fault.get("result", {})
                self._record(tool, args, result=res, tokens=tokens)
                return res
            err = "timeout" if kind == "timeout" else str(fault.get("code", "error"))
            self._record(tool, args, error=err, tokens=tokens)
            raise ToolError(err)
        if tool not in self.tools:
            self._record(tool, args, error="unknown_tool", tokens=tokens)
            raise ToolError("unknown_tool")
        try:
            res = self.tools[tool](args, self.state)
        except ToolError as exc:
            self._record(tool, args, error=str(exc), tokens=tokens)
            raise
        self._record(tool, args, result=res, tokens=tokens)
        return res


def replay_tools(recorded: Trace) -> Dict[str, Callable[[dict, dict], Any]]:
    """Phát lại phản hồi đã ghi: khớp theo (tool, tham số chuẩn hóa), dùng lần lượt."""
    queues: Dict[str, List[Event]] = defaultdict(list)
    for e in recorded.events:
        queues[call_hash(e.tool, e.args)].append(e)

    def make(tool):
        def fn(args, state):
            q = queues.get(call_hash(tool, args))
            if not q:
                raise ToolError("replay_miss")
            e = q.pop(0) if len(q) > 1 else q[0]
            if e.error is not None:
                raise ToolError(e.error)
            return e.result
        return fn

    return {t: make(t) for t in {e.tool for e in recorded.events}}
