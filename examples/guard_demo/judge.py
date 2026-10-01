"""Judge LLM mẫu cho plugin semantic_args, dùng API tương thích OpenAI.

Cần: pip install openai; biến môi trường OPENAI_API_KEY, OPENAI_MODEL (và OPENAI_BASE_URL nếu dùng endpoint riêng).
Chạy: toolcheck run spec.json --trace trace.jsonl --judge judge:judge
Lưu ý: prompt (gồm args và kết quả tool) được gửi tới endpoint này; che dữ liệu nhạy cảm trước.
"""

import os

from openai import OpenAI

_client = None


def judge(prompt: str) -> str:
    global _client
    _client = _client or OpenAI(timeout=60)
    resp = _client.chat.completions.create(
        model=os.environ["OPENAI_MODEL"],
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,  # model có thể dùng token cho suy luận trước khi trả lời
        temperature=0,
    )
    return resp.choices[0].message.content or ""
