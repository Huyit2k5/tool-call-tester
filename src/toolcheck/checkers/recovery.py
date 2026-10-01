"""Checker phục hồi: sau lỗi, agent có đổi tham số/chiến lược hay retry y hệt.

cfg: max_identical_retries (mặc định 0), require_recovery (mặc định True),
alternatives: {tool: [tool thay thế được chấp nhận]},
accept_final_answer (mặc định True): nếu lỗi là lời gọi CUỐI và agent kết thúc bằng câu trả lời cho
người dùng (ví dụ hỏi lại, xin chọn khác) thì coi là đã báo lại hợp lệ. Checker không đánh giá nội dung
câu trả lời có trung thực không; dùng semantic_args cho việc đó.
"""

from __future__ import annotations

from ..trace import Trace, call_hash


def check(trace: Trace, cfg: dict):
    from . import Finding

    max_same = cfg.get("max_identical_retries", 0)
    alts = cfg.get("alternatives", {})
    findings = []
    ev = trace.events

    # retry y hệt liên tiếp sau lỗi
    for i, e in enumerate(ev):
        if e.error is None:
            continue
        h, n = call_hash(e.tool, e.args), 0
        for nxt in ev[i + 1:]:
            if nxt.tool == e.tool and call_hash(nxt.tool, nxt.args) == h:
                n += 1
                if n > max_same:
                    findings.append(Finding(
                        "recovery",
                        f"'{e.tool}' lỗi ({e.error}) rồi retry y hệt lần {n}, không đổi tham số/chiến lược",
                        nxt.step,
                    ))
                    break
                if nxt.error is None:
                    break
            else:
                break

    # phải có lời gọi thành công sau lỗi cuối cùng của mỗi tool
    if cfg.get("require_recovery", True):
        last_err = {}
        for i, e in enumerate(ev):
            if e.error is not None:
                last_err[e.tool] = i
        for tool, i in last_err.items():
            ok_tools = {tool, *alts.get(tool, [])}
            escalated = cfg.get("accept_final_answer", True) and trace.final_answer and i == len(ev) - 1
            if not escalated and not any(x.tool in ok_tools and x.error is None for x in ev[i + 1:]):
                findings.append(Finding("recovery", f"lỗi của '{tool}' không được phục hồi", ev[i].step))
    return findings
