"""Đọc và kiểm tra test spec (JSON), báo lỗi rõ vị trí."""

from __future__ import annotations

import json

from .checkers.loop import DEFAULTS as LOOP_KEYS
from .checkers.schema import FORMATS, TYPES

TOP_KEYS = {"name", "selection", "schema", "provenance", "loop", "recovery", "budget", "final_state", "checks"}
RECOVERY_KEYS = {"max_identical_retries", "require_recovery", "alternatives", "accept_final_answer"}
PROVENANCE_KEYS = {"inputs", "rules"}
RULE_KEYS = {"tool", "arg", "from_result_of", "allow_input"}
SELECTION_KEYS = {"must_call", "must_not_call", "order"}
BUDGET_KEYS = {"max_steps", "max_tokens", "max_seconds"}
SCHEMA_TOOL_KEYS = {"required", "properties", "additional_properties"}
PROP_KEYS = {"type", "enum", "format"}


class SpecError(ValueError):
    pass


def _unknown(path: str, got: dict, allowed) -> None:
    extra = set(got) - set(allowed)
    if extra:
        raise SpecError(f"{path}: khóa lạ {sorted(extra)}; hợp lệ: {sorted(allowed)}")


def validate(spec: dict) -> dict:
    if not isinstance(spec, dict):
        raise SpecError("spec phải là object JSON")
    _unknown("spec", spec, TOP_KEYS)

    sel = spec.get("selection", {})
    _unknown("selection", sel, SELECTION_KEYS)
    for k in sel:
        if not (isinstance(sel[k], list) and all(isinstance(x, str) for x in sel[k])):
            raise SpecError(f"selection.{k}: phải là danh sách chuỗi")

    _unknown("loop", spec.get("loop", {}), LOOP_KEYS)
    for k, v in spec.get("loop", {}).items():
        if k == "allow_polling":
            if not isinstance(v, list):
                raise SpecError("loop.allow_polling: phải là danh sách")
        elif not isinstance(v, int) or v < 1:
            raise SpecError(f"loop.{k}: phải là số nguyên >= 1")

    _unknown("budget", spec.get("budget", {}), BUDGET_KEYS)
    for k, v in spec.get("budget", {}).items():
        if not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0:
            raise SpecError(f"budget.{k}: phải là số không âm")

    prov = spec.get("provenance", {})
    _unknown("provenance", prov, PROVENANCE_KEYS)
    for i, r in enumerate(prov.get("rules", [])):
        _unknown(f"provenance.rules[{i}]", r, RULE_KEYS)
        if "tool" not in r or "arg" not in r:
            raise SpecError(f"provenance.rules[{i}]: cần 'tool' và 'arg'")

    _unknown("recovery", spec.get("recovery", {}), RECOVERY_KEYS)
    _unknown("final_state", spec.get("final_state", {}), {"equals"})

    checks = spec.get("checks", {})
    if not isinstance(checks, dict) or not all(isinstance(v, dict) for v in checks.values()):
        raise SpecError("checks: phải là object {tên_plugin: {cấu hình}}")

    schema = spec.get("schema", {})
    _unknown("schema", schema, {"tools"})
    for tool, s in schema.get("tools", {}).items():
        base = f"schema.tools.{tool}"
        _unknown(base, s, SCHEMA_TOOL_KEYS)
        for pname, p in s.get("properties", {}).items():
            _unknown(f"{base}.properties.{pname}", p, PROP_KEYS)
            if "type" in p and p["type"] not in TYPES:
                raise SpecError(f"{base}.properties.{pname}.type: '{p['type']}' không hợp lệ; hợp lệ: {sorted(TYPES)}")
            if "format" in p and p["format"] not in FORMATS:
                raise SpecError(f"{base}.properties.{pname}.format: '{p['format']}' không hợp lệ; hợp lệ: {sorted(FORMATS)}")
    return spec


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if path.lower().endswith((".yaml", ".yml")):
        try:
            import yaml
        except ImportError as exc:
            raise SpecError("đọc YAML cần cài: pip install toolcheck[yaml]") from exc
        try:
            return validate(yaml.safe_load(text))
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            where = f" ở dòng {mark.line + 1}, cột {mark.column + 1}" if mark else ""
            raise SpecError(f"{path}: YAML sai{where}") from exc
    try:
        spec = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SpecError(f"{path}: JSON sai ở dòng {exc.lineno}, cột {exc.colno}: {exc.msg}") from exc
    return validate(spec)
