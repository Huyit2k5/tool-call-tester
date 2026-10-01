"""Checker schema tham số, tự viết, không dùng thư viện ngoài.

Cú pháp mỗi tool: {"required": [...], "properties": {tên: {type, enum, format}}}
"""

from __future__ import annotations

import re
from datetime import date, datetime

from ..trace import Trace

TYPES = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
}


def _iso_date(v: str) -> bool:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        return False
    try:
        date.fromisoformat(v)
        return True
    except ValueError:
        return False


def _iso_datetime(v: str) -> bool:
    try:
        datetime.fromisoformat(v.replace("Z", "+00:00"))
        return "T" in v or " " in v
    except ValueError:
        return False


FORMATS = {"iso-date": _iso_date, "iso-datetime": _iso_datetime}


def check(trace: Trace, cfg: dict):
    from . import Finding

    findings = []
    schemas = cfg.get("tools", {})
    for e in trace.events:
        sch = schemas.get(e.tool)
        if sch is None:
            continue
        props = sch.get("properties", {})
        for name in sch.get("required", []):
            if name not in e.args:
                findings.append(Finding("schema", f"{e.tool}: thiếu tham số bắt buộc '{name}'", e.step))
        for name, value in e.args.items():
            p = props.get(name)
            if p is None:
                if sch.get("additional_properties") is False:
                    findings.append(Finding("schema", f"{e.tool}: tham số lạ '{name}'", e.step))
                continue
            t = p.get("type")
            if t and not TYPES[t](value):
                findings.append(Finding("schema", f"{e.tool}.{name}: cần kiểu {t}, nhận {type(value).__name__}", e.step))
                continue
            if "enum" in p and value not in p["enum"]:
                findings.append(Finding("schema", f"{e.tool}.{name}: {value!r} không thuộc {p['enum']}", e.step))
            fmt = p.get("format")
            if fmt and isinstance(value, str) and not FORMATS[fmt](value):
                findings.append(Finding("schema", f"{e.tool}.{name}: {value!r} không đúng định dạng {fmt}", e.step))
    return findings
