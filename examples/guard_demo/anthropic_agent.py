"""Tích hợp thật: vòng lặp tool-use của Anthropic SDK, bọc mọi lời gọi tool bằng LoopGuard,
rồi xuất trace để kiểm bằng toolcheck.

Cần: pip install anthropic   và biến môi trường ANTHROPIC_API_KEY.
Chạy: python examples/guard_demo/anthropic_agent.py
Sau đó: toolcheck run spec.json --trace messages.json --format anthropic
"""

import json
import os

import anthropic

from toolcheck.guard import GuardError, LoopGuard

MODEL = "claude-sonnet-5-5"
TOOLS = [{
    "name": "search_flights",
    "description": "Tìm chuyến bay theo ngày.",
    "input_schema": {"type": "object", "properties": {"date": {"type": "string"}}, "required": ["date"]},
}]


def search_flights(date):
    return {"flights": []}  # luôn rỗng: dễ khiến model gọi lặp


IMPL = {"search_flights": search_flights}


def main():
    client = anthropic.Anthropic()
    guard = LoopGuard(max_repeat=3, max_steps=15)
    messages = [{"role": "user", "content": "Tìm chuyến bay HAN-SGN ngày 2026-10-01, thử đến khi có kết quả."}]
    history = list(messages)
    for _ in range(30):
        resp = client.messages.create(model=MODEL, max_tokens=1024, tools=TOOLS, messages=history)
        history.append({"role": "assistant", "content": [b.model_dump() for b in resp.content],
                        "usage": {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}})
        uses = [b for b in resp.content if b.type == "tool_use"]
        if not uses:
            break
        results = []
        for u in uses:
            try:
                out = guard.call(u.name, u.input, IMPL[u.name])
                results.append({"type": "tool_result", "tool_use_id": u.id, "content": json.dumps(out)})
            except GuardError as exc:
                print("GUARD chặn:", exc)
                results.append({"type": "tool_result", "tool_use_id": u.id, "is_error": True,
                                "content": f"Bị chặn: {exc}. Hãy đổi chiến lược hoặc trả lời người dùng."})
        history.append({"role": "user", "content": results})
    with open(os.path.join(os.path.dirname(__file__), "messages.json"), "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
