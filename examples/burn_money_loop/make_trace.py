"""Tạo trace của một agent giả bị kẹt: gọi search_flights y hệt 40 lần."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from toolcheck.trace import Event, Trace  # noqa: E402

trace = Trace()
for i in range(1, 41):
    trace.append(Event(
        step=i,
        tool="search_flights",
        args={"from": "HAN", "to": "SGN", "date": "2026-10-01"},
        result={"flights": []},
        ts=1000.0 + i,
        tokens=1200,
    ))
out = os.path.join(os.path.dirname(__file__), "trace.jsonl")
trace.save(out)
print(f"đã ghi {len(trace)} bước vào {out}")
