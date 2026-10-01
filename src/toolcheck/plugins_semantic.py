"""Plugin `semantic_args`: dùng LLM judge kiểm tham số có hợp lý theo ngữ nghĩa không.

KHÔNG bật mặc định và KHÔNG gắn SDK nào: judge là một hàm do bạn truyền vào.

    from toolcheck.plugins_semantic import set_judge
    set_judge(lambda prompt: my_llm(prompt))     # trả về chuỗi hoặc dict

Judge trả về một trong:  {"ok": bool, "reason": str}  |  chuỗi bắt đầu bằng PASS / FAIL (kèm lý do).
Spec:
  "checks": {"semantic_args": {
      "task": "Dời họp sprint sang chiều thứ Sáu",
      "rules": [{"tool": "reschedule", "criterion": "slot phải là chiều thứ Sáu"}]}}
Dữ liệu trace được gửi cho judge: hãy che thông tin nhạy cảm trước khi dùng (xem docs/plugins.md).
"""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

from .checkers import Finding
from .plugins import register

Judge = Callable[[str], Any]
_judge: Optional[Judge] = None


def set_judge(fn: Optional[Judge]) -> None:
    global _judge
    _judge = fn


def build_prompt(task: str, criterion: str, event, prior) -> str:
    history = [{"tool": p.tool, "args": p.args, "result": p.result, "error": p.error} for p in prior]
    return (
        "Bạn là bộ chấm tool-call. Chỉ trả lời JSON {\"ok\": true|false, \"reason\": \"...\"}.\n"
        f"Nhiệm vụ của người dùng: {task}\n"
        f"Lịch sử tool trước đó: {json.dumps(history, ensure_ascii=False)}\n"
        f"Lời gọi cần chấm: {json.dumps({'tool': event.tool, 'args': event.args}, ensure_ascii=False)}\n"
        f"Tiêu chí: {criterion}\n"
    )


def parse_verdict(raw: Any):
    """Trả (ok, reason); ném ValueError nếu không hiểu được."""
    if isinstance(raw, dict) and "ok" in raw:
        return bool(raw["ok"]), str(raw.get("reason", ""))
    if isinstance(raw, str):
        text = raw.strip()
        try:
            obj = json.loads(text)
            if isinstance(obj, dict) and "ok" in obj:
                return bool(obj["ok"]), str(obj.get("reason", ""))
        except ValueError:
            pass
        head = text.upper()
        if head.startswith("PASS"):
            return True, text[4:].strip(" :-")
        if head.startswith("FAIL"):
            return False, text[4:].strip(" :-")
    raise ValueError(f"judge trả về định dạng không hiểu được: {raw!r}")


@register("semantic_args")
def check(trace, cfg: dict):
    if _judge is None:
        raise ValueError("semantic_args cần judge: gọi toolcheck.plugins_semantic.set_judge(fn) "
                         "hoặc dùng --judge module:func")
    findings = []
    task = cfg.get("task", "")
    cache: dict = {}
    for rule in cfg.get("rules", []):
        for i, e in enumerate(trace.events):
            if e.tool != rule["tool"]:
                continue
            prompt = build_prompt(task, rule["criterion"], e, trace.events[:i])
            if prompt not in cache:
                cache[prompt] = _judge(prompt)
            try:
                ok, reason = parse_verdict(cache[prompt])
            except ValueError as exc:
                findings.append(Finding("semantic_args", f"{e.tool}: {exc}", e.step))
                continue
            if not ok:
                findings.append(Finding("semantic_args", f"{e.tool}: vi phạm '{rule['criterion']}'"
                                        + (f" ({reason})" if reason else ""), e.step))
    return findings
