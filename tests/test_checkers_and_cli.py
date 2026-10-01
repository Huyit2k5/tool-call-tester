import json
import os

import pytest

from toolcheck import cli, spec as spec_mod
from toolcheck.checkers import budget, schema, selection
from toolcheck.trace import Event, Trace

EX = os.path.join(os.path.dirname(__file__), "..", "examples")


def T(*events):
    return Trace([Event(step=i, **e) for i, e in enumerate(events, 1)])


def test_selection():
    t = T({"tool": "a"}, {"tool": "c"})
    f = selection.check(t, {"must_call": ["b"], "must_not_call": ["c"], "order": ["a", "b"]})
    assert len(f) == 3


def test_schema():
    cfg = {"tools": {"t": {"required": ["d"], "properties": {"d": {"type": "string", "format": "iso-date"}, "n": {"type": "integer"}}}}}
    assert schema.check(T({"tool": "t", "args": {"d": "2026-10-01", "n": 1}}), cfg) == []
    assert len(schema.check(T({"tool": "t", "args": {"d": "2026-13-01", "n": True}}), cfg)) == 2
    assert len(schema.check(T({"tool": "t", "args": {}}), cfg)) == 1


def test_budget():
    t = T({"tool": "a", "tokens": 10, "ts": 0.0}, {"tool": "a", "tokens": 10, "ts": 5.0})
    assert len(budget.check(t, {"max_steps": 1, "max_tokens": 5, "max_seconds": 1})) == 3


def test_spec_errors():
    with pytest.raises(spec_mod.SpecError, match="khóa lạ"):
        spec_mod.validate({"loops": {}})
    with pytest.raises(spec_mod.SpecError, match="loop.max_repeat_same_call"):
        spec_mod.validate({"loop": {"max_repeat_same_call": 0}})


def test_bad_json_reports_line(tmp_path):
    p = tmp_path / "s.json"
    p.write_text('{\n  "name": \n}', encoding="utf-8")
    with pytest.raises(spec_mod.SpecError, match="dòng 3"):
        spec_mod.load(str(p))


def run_example(name, tmp_path):
    out = tmp_path / "r.json"
    code = cli.main(["run", f"{EX}/{name}/spec.json", "--trace", f"{EX}/{name}/trace.jsonl", "--json", str(out)])
    return code, json.loads(out.read_text(encoding="utf-8"))


def test_cli_good(tmp_path):
    code, rep = run_example("good_agent", tmp_path)
    assert code == 0 and rep["passed"]


def test_cli_bad_schema(tmp_path):
    code, rep = run_example("bad_schema", tmp_path)
    assert code == 1 and rep["layers"]["schema"] and rep["layers"]["selection"]


def test_cli_loop_demo(tmp_path):
    import runpy
    runpy.run_path(f"{EX}/burn_money_loop/make_trace.py")
    code, rep = run_example("burn_money_loop", tmp_path)
    assert code == 1
    assert rep["layers"]["loop"][0]["step"] == 3
    assert rep["tokens_saved"] == 37 * 1200
