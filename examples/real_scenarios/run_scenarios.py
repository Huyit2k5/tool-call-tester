"""Chạy model thật (API tương thích OpenAI) qua vài kịch bản, rồi kiểm bằng toolcheck để đo báo oan/bỏ sót.

Cần: OPENAI_API_KEY, OPENAI_MODEL (+ OPENAI_BASE_URL nếu endpoint riêng).
Chạy: python examples/real_scenarios/run_scenarios.py [số_lần=3]
Ghi out/<kịch bản>_<n>.json (messages) và in bảng tổng hợp. Không ghi khóa vào file.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
sys.stdout.reconfigure(encoding="utf-8")

from openai import OpenAI  # noqa: E402

from toolcheck.adapters import convert  # noqa: E402
from toolcheck.mock import Sandbox, ToolError  # noqa: E402
from toolcheck.runner import run  # noqa: E402
from toolcheck.spec import validate  # noqa: E402

MAX_TURNS = 10


def fn(name, desc, props, required):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required}}}


def scenario_recover_400():
    tools = [
        fn("find_meeting", "Tìm cuộc họp theo tên.", {"query": {"type": "string"}}, ["query"]),
        fn("reschedule_meeting", "Dời cuộc họp sang khung giờ mới (ISO 8601).",
           {"meeting_id": {"type": "string"}, "slot": {"type": "string"}}, ["meeting_id", "slot"]),
    ]
    def reschedule(args, state):
        state["slot"] = args["slot"]
        return {"ok": True}
    sb = Sandbox({"find_meeting": lambda a, s: {"id": "m42", "title": "Họp sprint"},
                  "reschedule_meeting": reschedule},
                 faults=[{"tool": "reschedule_meeting", "on_call": 1, "kind": "error",
                          "code": "400 Bad Request: khung giờ này đã có người đặt, hãy chọn giờ khác"}])
    spec = {"selection": {"must_call": ["find_meeting", "reschedule_meeting"], "order": ["find_meeting", "reschedule_meeting"]},
            "schema": {"tools": {"reschedule_meeting": {"required": ["meeting_id", "slot"],
                                                         "properties": {"slot": {"type": "string", "format": "iso-datetime"}}}}},
            "provenance": {"rules": [{"tool": "reschedule_meeting", "arg": "meeting_id", "from_result_of": "find_meeting"}]},
            "loop": {}, "recovery": {}, "budget": {"max_steps": 8}}
    return "Dời cuộc họp sprint sang 14:00 ngày 2026-10-03.", tools, sb, spec


def scenario_invented_id():
    tools = [
        fn("list_bookings", "Liệt kê booking của người dùng.", {}, []),
        fn("cancel_booking", "Hủy một booking theo booking_id.", {"booking_id": {"type": "string"}}, ["booking_id"]),
    ]
    sb = Sandbox({"list_bookings": lambda a, s: [{"booking_id": "BK-1029", "dest": "SGN"},
                                                  {"booking_id": "BK-2210", "dest": "DAD"}],
                  "cancel_booking": lambda a, s: {"cancelled": a["booking_id"]}})
    spec = {"selection": {"must_call": ["cancel_booking"]},
            "provenance": {"rules": [{"tool": "cancel_booking", "arg": "booking_id", "from_result_of": "list_bookings"}]},
            "loop": {}, "recovery": {}, "budget": {"max_steps": 6}}
    return "Hủy chuyến bay đi Đà Nẵng của tôi.", tools, sb, spec


def scenario_cycle():
    tools = [
        fn("get_status", "Lấy trạng thái job.", {"job_id": {"type": "string"}}, ["job_id"]),
        fn("get_logs", "Lấy log của job.", {"job_id": {"type": "string"}}, ["job_id"]),
    ]
    sb = Sandbox({"get_status": lambda a, s: {"status": "unknown", "hint": "xem get_logs"},
                  "get_logs": lambda a, s: {"lines": [], "hint": "log rỗng, xem get_status"}})
    spec = {"loop": {}, "recovery": {}, "budget": {"max_steps": 8}}
    return ("Job J-1 đang ở trạng thái cuối cùng nào (done hoặc failed)? "
            "Chỉ trả lời khi đã biết chắc; dùng tool để tìm."), tools, sb, spec


SCENARIOS = {"recover_400": scenario_recover_400, "invented_id": scenario_invented_id, "cycle": scenario_cycle}


def run_one(client, model, name):
    prompt, tools, sb, spec = SCENARIOS[name]()
    history = [{"role": "user", "content": prompt}]
    for _ in range(MAX_TURNS):
        resp = client.chat.completions.create(model=model, messages=history, tools=tools, max_tokens=2000)
        msg = resp.choices[0].message
        history.append({**msg.model_dump(exclude_none=True), "usage": {"total_tokens": resp.usage.total_tokens}})
        if not msg.tool_calls:
            break
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
                out = json.dumps(sb.call(tc.function.name, args), ensure_ascii=False)
            except ToolError as exc:
                out = json.dumps({"error": str(exc)}, ensure_ascii=False)
            except Exception as exc:  # args hỏng, tool lạ...
                out = json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False)
            history.append({"role": "tool", "tool_call_id": tc.id, "content": out})
    return history, spec


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    client, model = OpenAI(timeout=120), os.environ["OPENAI_MODEL"]
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    print(f"{'kịch bản':<13}{'lần':<4}{'bước':<5}{'tool-calls':<42}FAIL")
    for name in SCENARIOS:
        for i in range(1, n + 1):
            history, spec = run_one(client, model, name)
            with open(os.path.join(HERE, "out", f"{name}_{i}.json"), "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=1)
            trace = convert("openai", history)
            rep = run(validate(spec), trace)
            fails = "; ".join(f"{k}:{len(v)}" for k, v in rep.layers.items() if v) or "-"
            calls = ",".join(f"{e.tool}{'!' if e.error else ''}" for e in trace)
            print(f"{name:<13}{i:<4}{len(trace):<5}{calls[:40]:<42}{fails}")


if __name__ == "__main__":
    main()
