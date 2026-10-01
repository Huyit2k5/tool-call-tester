"""Checker vòng lặp: lặp y hệt, chu kỳ A->B->A->B, và không tiến triển."""

from __future__ import annotations

from collections import Counter
from typing import List

from ..trace import Trace, call_hash, result_hash

DEFAULTS = {
    "max_repeat_same_call": 3,   # báo khi cùng một lời gọi xuất hiện đủ số lần này
    "max_cycle_len": 4,          # độ dài chu kỳ tối đa cần dò
    "min_cycle_repeats": 2,      # số lần chu kỳ lặp liên tiếp thì báo
    "max_no_progress": 3,        # số bước liên tiếp cùng kết quả thì báo
    "allow_polling": [],         # tool được phép gọi lặp (chờ trạng thái đổi)
}


def check(trace: Trace, cfg: dict):
    from . import Finding

    c = {**DEFAULTS, **cfg}
    polling = set(c["allow_polling"])
    events = [e for e in trace.events if e.tool not in polling]
    findings: List[Finding] = []
    layer = "loop"

    # 1. Lặp y hệt
    hashes = [call_hash(e.tool, e.args) for e in events]
    counts: Counter = Counter()
    reported = set()
    for e, h in zip(events, hashes):
        counts[h] += 1
        if counts[h] >= c["max_repeat_same_call"] and h not in reported:
            reported.add(h)
            findings.append(Finding(
                layer,
                f"'{e.tool}' bị gọi lặp y hệt {counts[h]} lần (ngưỡng {c['max_repeat_same_call']})",
                e.step,
            ))

    # 2. Chu kỳ độ dài >= 2 (độ dài 1 đã thuộc mục 1)
    reps = c["min_cycle_repeats"]
    n = len(hashes)
    for k in range(2, c["max_cycle_len"] + 1):
        need = k * reps
        i = 0
        while i + need <= n:
            block = hashes[i:i + k]
            if len(set(block)) > 1 and all(hashes[i + j] == block[j % k] for j in range(need)):
                # mở rộng đến hết chuỗi lặp
                end = i + need
                while end < n and hashes[end] == block[(end - i) % k]:
                    end += 1
                names = "->".join(e.tool for e in events[i:i + k])
                findings.append(Finding(
                    layer,
                    f"chu kỳ {names} lặp {(end - i) // k} lần liên tiếp",
                    events[i + need - 1].step,
                ))
                i = end
            else:
                i += 1

    # 3. Không tiến triển: nhiều bước liên tiếp kết quả giống hệt
    run, prev = 0, None
    for e in events:
        rh = result_hash(e.result, e.error)
        run = run + 1 if rh == prev else 1
        prev = rh
        if run == c["max_no_progress"]:
            findings.append(Finding(
                layer,
                f"{run} bước liên tiếp cho kết quả giống hệt (không tiến triển)",
                e.step,
            ))
    return findings
