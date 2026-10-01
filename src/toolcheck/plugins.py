"""Giao diện plugin: viết checker riêng và đăng ký để dùng trong spec qua khóa `checks`.

    from toolcheck.plugins import register
    from toolcheck.checkers import Finding

    @register("no_empty_query")
    def check(trace, cfg):                      # trả về list[Finding]
        return [Finding("no_empty_query", "query rỗng", e.step)
                for e in trace if e.tool == "search" and not e.args.get("q")]

Spec:  {"checks": {"no_empty_query": {}}}      # cfg = nội dung object này
Nạp plugin: `toolcheck run ... --plugin my_module` hoặc entry point nhóm `toolcheck.checkers`.
"""

from __future__ import annotations

import importlib
from typing import Callable, Dict, List

from .checkers import CHECKERS, Finding
from .trace import Trace

CheckerFn = Callable[[Trace, dict], List[Finding]]
REGISTRY: Dict[str, CheckerFn] = {}


def register(name: str, fn: CheckerFn = None):
    """Dùng như decorator `@register("ten")` hoặc `register("ten", fn)`."""
    def deco(f: CheckerFn) -> CheckerFn:
        if name in CHECKERS:
            raise ValueError(f"'{name}' trùng tên checker có sẵn")
        if name in REGISTRY and REGISTRY[name] is not f:
            raise ValueError(f"plugin '{name}' đã được đăng ký")
        REGISTRY[name] = f
        return f
    return deco(fn) if fn is not None else deco


def load_module(path: str) -> None:
    """Import module để các lệnh @register chạy."""
    try:
        importlib.import_module(path)
    except ImportError as exc:
        raise ValueError(f"không nạp được plugin '{path}': {exc}") from exc


def load_entry_points() -> None:
    try:
        from importlib.metadata import entry_points
        eps = entry_points()
        group = eps.select(group="toolcheck.checkers") if hasattr(eps, "select") \
            else eps.get("toolcheck.checkers", [])
    except Exception:  # môi trường không có metadata thì bỏ qua
        return
    for ep in group:
        fn = ep.load()
        if ep.name not in REGISTRY:
            register(ep.name, fn)


def get(name: str) -> CheckerFn:
    if name not in REGISTRY:
        load_entry_points()
    if name not in REGISTRY:
        raise KeyError(name)
    return REGISTRY[name]
