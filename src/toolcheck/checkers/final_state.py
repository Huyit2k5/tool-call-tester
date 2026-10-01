"""Kiểm tra trạng thái cuối của tool giả lập: so khớp tập con (subset) đệ quy."""

from __future__ import annotations

_MISSING = object()


def _diff(expected, actual, path, out):
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            out.append(f"{path or 'state'}: cần object, nhận {actual!r}")
            return
        for k, v in expected.items():
            _diff(v, actual.get(k, _MISSING), f"{path}.{k}" if path else k, out)
    elif actual is _MISSING:
        out.append(f"{path}: thiếu (cần {expected!r})")
    elif expected != actual:
        out.append(f"{path}: cần {expected!r}, nhận {actual!r}")


def check_state(state, cfg: dict):
    from . import Finding

    if state is None:
        return [Finding("final_state", "spec có final_state nhưng không có state để so (dùng --state)")]
    diffs: list = []
    _diff(cfg.get("equals", {}), state, "", diffs)
    return [Finding("final_state", d) for d in diffs]
