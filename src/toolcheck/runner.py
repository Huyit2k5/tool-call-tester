"""Chạy spec trên trace, trả về kết quả theo từng lớp."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .checkers import CHECKERS, Finding, check_state
from . import plugins, plugins_semantic  # noqa: F401  (nạp semantic_args)
from .spec import SpecError
from .trace import Trace

LAYERS = ["selection", "schema", "provenance", "loop", "recovery", "budget"]


@dataclass
class Report:
    name: str
    steps: int
    tokens: int
    layers: Dict[str, List[Finding]] = field(default_factory=dict)
    tokens_saved: int = 0

    @property
    def passed(self) -> bool:
        return not any(self.layers.values())

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "steps": self.steps,
            "tokens": self.tokens,
            "tokens_saved": self.tokens_saved,
            "layers": {k: [f.to_dict() for f in v] for k, v in self.layers.items()},
        }


def run(spec: dict, trace: Trace, state=None) -> Report:
    report = Report(spec.get("name", "unnamed"), len(trace), trace.total_tokens)
    for layer in LAYERS:
        if layer in spec:
            report.layers[layer] = CHECKERS[layer](trace, spec[layer])

    for name, cfg in spec.get("checks", {}).items():
        try:
            fn = plugins.get(name)
        except KeyError:
            raise SpecError(f"checks.{name}: plugin chưa được đăng ký (dùng --plugin module hoặc entry point)") from None
        report.layers[name] = fn(trace, cfg)

    if "final_state" in spec:
        report.layers["final_state"] = check_state(state, spec["final_state"])

    loop_steps = [f.step for f in report.layers.get("loop", []) if f.step is not None]
    if loop_steps:
        first = min(loop_steps)
        report.tokens_saved = sum(e.tokens for e in trace.events if e.step > first)
    return report
