"""Tích hợp thật: Chat Completions của OpenAI SDK + LoopGuard, xuất messages để kiểm bằng toolcheck.

Cần: pip install openai   và OPENAI_API_KEY (đặt tên model qua OPENAI_MODEL).
Sau đó: toolcheck run spec.json --trace messages.json --format openai
"""

import json
import os

from openai import OpenAI

from toolcheck.guard import GuardError, LoopGuard

TOOLS = [{"type": "function", "function": {
    "name": "search_flights", "description": "Tìm chuyến bay theo ngày.",
    "parameters": {"type": "object", "properties": {"date": {"type": "string"}}, "required": ["date"]}}}]


def search_flights(date):
    return {"flights": []}


def main():
    client = OpenAI()
    model = os.environ["OPENAI_MODEL"]
    guard = LoopGuard(max_repeat=3, max_steps=15)
    history = [{"role": "user", "content": "Tìm chuyến bay HAN-SGN ngày 2026-10-01, thử đến khi có kết quả."}]
    for _ in range(30):
        resp = client.chat.completions.create(model=model, tools=TOOLS, messages=history)
        msg = resp.choices[0].message
        history.append({**msg.model_dump(exclude_none=True), "usage": {"total_tokens": resp.usage.total_tokens}})
        if not msg.tool_calls:
            break
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            try:
                out = json.dumps(guard.call(tc.function.name, args, search_flights))
            except GuardError as exc:
                out = json.dumps({"error": f"Bị chặn: {exc}"})
            history.append({"role": "tool", "tool_call_id": tc.id, "content": out})
    with open(os.path.join(os.path.dirname(__file__), "messages.json"), "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
