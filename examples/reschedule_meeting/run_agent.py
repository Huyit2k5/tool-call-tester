"""Agent giả (kịch bản cố định) dời lịch họp trên Sandbox có chèn lỗi 400.

Chạy: python run_agent.py [--bad]   (--bad: agent retry y hệt và bịa ID)
Ghi trace[_bad].jsonl và state[_bad].json cạnh file này.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))

from toolcheck.mock import Sandbox, ToolError  # noqa: E402


def find_meeting(args, state):
    return {"id": "m42", "title": args["query"], "slot": "2026-10-02T09:00:00"}


def find_slot(args, state):
    return {"slots": ["2026-10-03T09:00:00", "2026-10-03T14:00:00"]}


def reschedule(args, state):
    state.setdefault("meetings", {})[args["meeting_id"]] = {"slot": args["slot"]}
    return {"ok": True}


def run(bad: bool = False):
    sb = Sandbox(
        {"find_meeting": find_meeting, "find_slot": find_slot, "reschedule_meeting": reschedule},
        faults=[{"tool": "reschedule_meeting", "on_call": 1, "kind": "error", "code": 400}],
        state={"meetings": {"m42": {"slot": "2026-10-02T09:00:00"}}},
    )
    meeting = sb.call("find_meeting", {"query": "họp sprint"}, tokens=300)
    slots = sb.call("find_slot", {"day": "2026-10-03"}, tokens=300)
    mid = "m99" if bad else meeting["id"]
    args = {"meeting_id": mid, "slot": slots["slots"][0]}
    for attempt in range(2):
        try:
            sb.call("reschedule_meeting", args, tokens=400)
            break
        except ToolError:
            if not bad:  # agent tốt đổi chiến lược: chọn khung giờ khác
                args = {"meeting_id": mid, "slot": slots["slots"][1]}
    return sb


if __name__ == "__main__":
    bad = "--bad" in sys.argv
    suffix = "_bad" if bad else ""
    sb = run(bad=bad)
    sb.trace.save(os.path.join(HERE, f"trace{suffix}.jsonl"))
    with open(os.path.join(HERE, f"state{suffix}.json"), "w", encoding="utf-8") as f:
        json.dump(sb.state, f, ensure_ascii=False, indent=2)
    print("wrote trace and state")
