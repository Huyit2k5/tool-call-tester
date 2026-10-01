"""Agent giả bị kẹt vòng lặp; LoopGuard chặn ở lần gọi thứ 3 (không cần API/khóa).

Chạy: python examples/guard_demo/offline_agent.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from toolcheck.guard import LoopDetected, LoopGuard  # noqa: E402


sys.stdout.reconfigure(encoding="utf-8")


def search_flights(**args):
    return {"flights": []}


guard = LoopGuard(max_repeat=3, max_steps=20)
try:
    for step in range(40):  # agent "mù" cứ gọi lại y hệt
        guard.call("search_flights", {"from": "HAN", "to": "SGN"}, search_flights, tokens=1200)
except LoopDetected as exc:
    print(f"GUARD: dừng ở bước {exc.step} ({exc}); đã gọi thật {len(guard.trace)}/40 lan, "
          f"tiết kiệm {(40 - len(guard.trace)) * 1200} token")
