"""Checker chọn tool: must_call, must_not_call, order."""

from __future__ import annotations

from ..trace import Trace


def check(trace: Trace, cfg: dict):
    from . import Finding

    findings = []
    called = [e.tool for e in trace.events]
    seen = set(called)

    for tool in cfg.get("must_call", []):
        if tool not in seen:
            findings.append(Finding("selection", f"thiếu lời gọi bắt buộc '{tool}'"))
    for e in trace.events:
        if e.tool in cfg.get("must_not_call", []):
            findings.append(Finding("selection", f"gọi tool bị cấm '{e.tool}'", e.step))

    order = cfg.get("order", [])
    pos = 0
    for tool in called:
        if pos < len(order) and tool == order[pos]:
            pos += 1
    if order and pos < len(order):
        findings.append(Finding("selection", f"sai thứ tự: cần {' -> '.join(order)}, dừng ở '{order[pos]}'"))
    return findings
