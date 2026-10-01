"""Checker nguồn gốc giá trị: tham số phải đến từ input hoặc kết quả tool trước (bắt lỗi bịa ID).

Luật: {"tool": t, "arg": a, "from_result_of": tool_khác (tùy chọn), "allow_input": bool}
Nếu không có from_result_of, nguồn hợp lệ là input hoặc kết quả của bất kỳ bước trước.
"""

from __future__ import annotations

from ..trace import Trace


def _contains(source, v) -> bool:
    if isinstance(source, dict):
        return any(_contains(x, v) for x in source.values())
    if isinstance(source, (list, tuple)):
        return any(_contains(x, v) for x in source)
    if isinstance(source, str) and isinstance(v, str):
        return v in source
    return source == v and type(source) is type(v)


def check(trace: Trace, cfg: dict):
    from . import Finding

    inputs = cfg.get("inputs", [])
    findings = []
    for rule in cfg.get("rules", []):
        for i, e in enumerate(trace.events):
            if e.tool != rule["tool"] or rule["arg"] not in e.args:
                continue
            v = e.args[rule["arg"]]
            src_tool = rule.get("from_result_of")
            prior = [p.result for p in trace.events[:i]
                     if p.error is None and (src_tool is None or p.tool == src_tool)]
            ok = any(_contains(r, v) for r in prior)
            if not ok and (src_tool is None or rule.get("allow_input")):
                ok = _contains(inputs, v)
            if not ok:
                where = f"kết quả của '{src_tool}'" if src_tool else "input hoặc kết quả trước đó"
                findings.append(Finding(
                    "provenance",
                    f"{e.tool}.{rule['arg']}={v!r} không có nguồn từ {where}",
                    e.step,
                ))
    return findings
