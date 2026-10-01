"""Checker tùy chỉnh mẫu: cấm tham số `q` rỗng khi gọi `search`, và giới hạn số lần gọi mỗi tool.

Spec:   {"checks": {"search_hygiene": {"max_calls_per_tool": 5}}}
Chạy:   toolcheck run spec.json --trace trace.jsonl --plugin my_checker
"""

from collections import Counter

from toolcheck.checkers import Finding
from toolcheck.plugins import register


@register("search_hygiene")
def check(trace, cfg):
    findings = [Finding("search_hygiene", "search với q rỗng", e.step)
                for e in trace if e.tool == "search" and not str(e.args.get("q", "")).strip()]
    limit = cfg.get("max_calls_per_tool")
    if limit:
        for tool, n in Counter(e.tool for e in trace).items():
            if n > limit:
                findings.append(Finding("search_hygiene", f"'{tool}' được gọi {n} lần (> {limit})"))
    return findings
