"""Runtime guard: bọc hàm gọi tool, chặn vòng lặp / vượt ngân sách ngay khi agent đang chạy.

    guard = LoopGuard(max_repeat=3, max_steps=20)
    result = guard.call(tool_name, args, fn)   # raise LoopDetected / BudgetExceeded

Lặp y hệt và chu kỳ bị chặn TRƯỚC khi gọi fn (không tốn lời gọi thật).
"Không tiến triển" chỉ biết sau khi có kết quả nên raise SAU lời gọi.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Iterable, Optional

from .checkers import loop
from .trace import Event, Trace

_OFF = 10 ** 9


class GuardError(Exception):
    pass


class LoopDetected(GuardError):
    def __init__(self, message: str, tool: str, step: int, result: Any = None):
        super().__init__(message)
        self.tool, self.step, self.result = tool, step, result


class BudgetExceeded(GuardError):
    def __init__(self, message: str, result: Any = None):
        super().__init__(message)
        self.result = result


class LoopGuard:
    def __init__(self, max_repeat: int = 3, max_steps: Optional[int] = None,
                 max_tokens: Optional[int] = None, max_seconds: Optional[float] = None,
                 max_cycle_len: int = 4, min_cycle_repeats: int = 2, max_no_progress: int = 3,
                 allow_polling: Iterable[str] = (), clock: Callable[[], float] = time.time):
        self.cfg = {
            "max_repeat_same_call": max_repeat, "max_cycle_len": max_cycle_len,
            "min_cycle_repeats": min_cycle_repeats, "max_no_progress": max_no_progress,
            "allow_polling": list(allow_polling),
        }
        self.max_steps, self.max_tokens, self.max_seconds = max_steps, max_tokens, max_seconds
        self.trace = Trace()
        self._clock = clock
        self._start: Optional[float] = None

    # --- kiểm tra ---
    def _check_budget_before(self) -> None:
        if self.max_steps is not None and len(self.trace) >= self.max_steps:
            raise BudgetExceeded(f"đã đủ {self.max_steps} bước")
        if self.max_seconds is not None and self._start is not None \
                and self._clock() - self._start > self.max_seconds:
            raise BudgetExceeded(f"quá {self.max_seconds}s")
        if self.max_tokens is not None and self.trace.total_tokens > self.max_tokens:
            raise BudgetExceeded(f"{self.trace.total_tokens} token vượt {self.max_tokens}")

    def _pre_loop(self, pending: Event) -> None:
        cfg = {**self.cfg, "max_no_progress": _OFF}
        probe = Trace(self.trace.events + [pending])
        hits = [f for f in loop.check(probe, cfg) if f.step == pending.step]
        if hits:
            raise LoopDetected(hits[0].message, pending.tool, pending.step)

    def _post_loop(self, event: Event, result: Any) -> None:
        cfg = {**self.cfg, "max_repeat_same_call": _OFF, "min_cycle_repeats": _OFF}
        hits = [f for f in loop.check(self.trace, cfg) if f.step == event.step]
        if hits:
            raise LoopDetected(hits[0].message, event.tool, event.step, result)

    # --- API ---
    def call(self, tool: str, args: dict, fn: Callable[..., Any], tokens: int = 0) -> Any:
        self._check_budget_before()
        if self._start is None:
            self._start = self._clock()
        pending = Event(step=len(self.trace) + 1, tool=tool, args=args, ts=self._clock(), tokens=tokens)
        self._pre_loop(pending)
        try:
            result = fn(**args) if isinstance(args, dict) else fn(args)
        except Exception as exc:
            pending.error = str(exc) or type(exc).__name__
            self.trace.append(pending)
            raise
        pending.result = result
        self.trace.append(pending)
        if self.max_tokens is not None and self.trace.total_tokens > self.max_tokens:
            raise BudgetExceeded(f"{self.trace.total_tokens} token vượt {self.max_tokens}", result)
        self._post_loop(pending, result)
        return result

    async def acall(self, tool: str, args: dict, fn: Callable[..., Any], tokens: int = 0) -> Any:
        """Bản async: fn là coroutine function."""
        self._check_budget_before()
        if self._start is None:
            self._start = self._clock()
        pending = Event(step=len(self.trace) + 1, tool=tool, args=args, ts=self._clock(), tokens=tokens)
        self._pre_loop(pending)
        try:
            result = await fn(**args)
        except Exception as exc:
            pending.error = str(exc) or type(exc).__name__
            self.trace.append(pending)
            raise
        pending.result = result
        self.trace.append(pending)
        self._post_loop(pending, result)
        return result
