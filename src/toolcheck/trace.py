"""Định dạng trace chuẩn (JSONL) và chuẩn hóa tham số để băm ổn định."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterable, List, Optional

FLOAT_DIGITS = 6


@dataclass
class Event:
    step: int
    tool: str
    args: dict = field(default_factory=dict)
    result: Any = None
    error: Optional[str] = None
    ts: Optional[float] = None
    tokens: int = 0

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "tool": self.tool,
            "args": self.args,
            "result": self.result,
            "error": self.error,
            "ts": self.ts,
            "tokens": self.tokens,
        }

    @classmethod
    def from_dict(cls, d: dict, default_step: int = 0) -> "Event":
        if "tool" not in d or not isinstance(d["tool"], str):
            raise ValueError("sự kiện thiếu trường 'tool' (chuỗi)")
        args = d.get("args") or {}
        if not isinstance(args, dict):
            raise ValueError("'args' phải là object")
        return cls(
            step=int(d.get("step", default_step)),
            tool=d["tool"],
            args=args,
            result=d.get("result"),
            error=d.get("error"),
            ts=d.get("ts"),
            tokens=int(d.get("tokens") or 0),
        )


def normalize_args(value: Any) -> Any:
    """Sắp xếp khóa, bỏ khoảng trắng thừa, làm tròn số thực."""
    if isinstance(value, dict):
        return {k: normalize_args(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [normalize_args(v) for v in value]
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, float):
        r = round(value, FLOAT_DIGITS)
        return int(r) if r == int(r) else r
    return value


def call_hash(tool: str, args: dict) -> str:
    payload = json.dumps([tool, normalize_args(args)], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def result_hash(result: Any, error: Optional[str] = None) -> str:
    payload = json.dumps([normalize_args(result), error], sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class Trace:
    def __init__(self, events: Optional[Iterable[Event]] = None, final_answer: Optional[str] = None):
        self.events: List[Event] = list(events or [])
        # Câu trả lời cuối của agent cho người dùng (nếu log có); dùng để biết agent đã báo lại sau lỗi.
        self.final_answer: Optional[str] = final_answer

    def __len__(self) -> int:
        return len(self.events)

    def __iter__(self):
        return iter(self.events)

    def append(self, event: Event) -> None:
        self.events.append(event)

    @property
    def total_tokens(self) -> int:
        return sum(e.tokens for e in self.events)

    @property
    def duration(self) -> float:
        stamps = [e.ts for e in self.events if e.ts is not None]
        return (max(stamps) - min(stamps)) if len(stamps) > 1 else 0.0

    @classmethod
    def from_jsonl(cls, text: str) -> "Trace":
        events, final = [], None
        for lineno, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict) and "final_answer" in obj and "tool" not in obj:
                    final = obj["final_answer"]
                    continue
                events.append(Event.from_dict(obj, default_step=len(events) + 1))
            except (ValueError, TypeError) as exc:
                raise ValueError(f"trace dòng {lineno}: {exc}") from exc
        return cls(events, final)

    @classmethod
    def load(cls, path: str) -> "Trace":
        with open(path, encoding="utf-8") as f:
            return cls.from_jsonl(f.read())

    def to_jsonl(self) -> str:
        out = "".join(json.dumps(e.to_dict(), ensure_ascii=False) + "\n" for e in self.events)
        if self.final_answer:
            out += json.dumps({"final_answer": self.final_answer}, ensure_ascii=False) + "\n"
        return out

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_jsonl())
