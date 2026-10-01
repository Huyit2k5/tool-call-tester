import glob
import json
import os
import sys

import pytest

from toolcheck import cli, plugins, plugins_semantic
from toolcheck.checkers import Finding
from toolcheck.report.html import to_html
from toolcheck.runner import run
from toolcheck.spec import SpecError, validate
from toolcheck.trace import Event, Trace

ROOT = os.path.join(os.path.dirname(__file__), "..")
CASES = sorted(glob.glob(os.path.join(ROOT, "failure-gallery", "cases", "*.json")))


def T(*events):
    return Trace([Event(step=i, **e) for i, e in enumerate(events, 1)])


@pytest.fixture(autouse=True)
def _reset():
    plugins_semantic.set_judge(None)
    yield
    plugins_semantic.set_judge(None)
    plugins.REGISTRY.pop("tmp_plugin", None)


# ---------- plugin interface ----------
def test_register_and_run_custom_checker():
    @plugins.register("tmp_plugin")
    def check(trace, cfg):
        return [Finding("tmp_plugin", "có tool x", e.step) for e in trace if e.tool == cfg["tool"]]

    spec = validate({"checks": {"tmp_plugin": {"tool": "x"}}})
    rep = run(spec, T({"tool": "x"}, {"tool": "y"}))
    assert not rep.passed and rep.layers["tmp_plugin"][0].step == 1


def test_register_rejects_builtin_and_unknown_plugin():
    with pytest.raises(ValueError, match="trùng"):
        plugins.register("loop", lambda t, c: [])
    with pytest.raises(SpecError, match="chưa được đăng ký"):
        run({"checks": {"nope": {}}}, Trace())
    with pytest.raises(SpecError):
        validate({"checks": {"a": 1}})


def test_example_plugin_via_cli(tmp_path, monkeypatch):
    d = os.path.join(ROOT, "examples", "plugin_demo")
    monkeypatch.syspath_prepend(d)
    try:
        code = cli.main(["run", f"{d}/spec.json", "--trace", f"{d}/trace.jsonl", "--plugin", "my_checker"])
    finally:
        plugins.REGISTRY.pop("search_hygiene", None)
        sys.modules.pop("my_checker", None)
    assert code == 1


def test_cli_unregistered_plugin_returns_2(tmp_path):
    spec = tmp_path / "s.json"
    spec.write_text(json.dumps({"checks": {"zzz": {}}}), encoding="utf-8")
    tr = tmp_path / "t.jsonl"
    tr.write_text("", encoding="utf-8")
    assert cli.main(["run", str(spec), "--trace", str(tr)]) == 2


# ---------- semantic_args ----------
SPEC = {"checks": {"semantic_args": {"task": "dời họp sang chiều thứ Sáu",
                                      "rules": [{"tool": "reschedule", "criterion": "slot là chiều thứ Sáu"}]}}}
TRACE = lambda: T({"tool": "reschedule", "args": {"slot": "2026-10-02T09:00"}})


def test_semantic_requires_judge():
    with pytest.raises(ValueError, match="judge"):
        run(SPEC, TRACE())


@pytest.mark.parametrize("verdict,passed", [
    ({"ok": True}, True), ({"ok": False, "reason": "sáng"}, False),
    ("PASS ok", True), ("FAIL: là buổi sáng", False), ('{"ok": false, "reason": "x"}', False)])
def test_semantic_verdict_formats(verdict, passed):
    plugins_semantic.set_judge(lambda prompt: verdict)
    assert run(SPEC, TRACE()).passed is passed


def test_semantic_bad_verdict_is_a_finding_and_prompt_has_context():
    seen = []
    plugins_semantic.set_judge(lambda p: seen.append(p) or "maybe?")
    rep = run(SPEC, TRACE())
    assert not rep.passed and "không hiểu" in rep.layers["semantic_args"][0].message
    assert "dời họp" in seen[0] and "2026-10-02T09:00" in seen[0] and "chiều thứ Sáu" in seen[0]


def test_semantic_caches_identical_prompts():
    n = []
    plugins_semantic.set_judge(lambda p: n.append(1) or {"ok": True})
    rule = {"tool": "t", "criterion": "c"}
    run({"checks": {"semantic_args": {"rules": [rule, dict(rule)]}}}, T({"tool": "t", "args": {}}))
    assert len(n) == 1  # hai luật trùng -> cùng prompt -> chỉ hỏi judge một lần


def test_cli_judge_option(tmp_path, monkeypatch):
    (tmp_path / "myjudge.py").write_text("def j(prompt):\n    return 'FAIL: sai'\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    spec = tmp_path / "s.json"
    spec.write_text(json.dumps(SPEC), encoding="utf-8")
    tr = tmp_path / "t.jsonl"
    TRACE().save(str(tr))
    assert cli.main(["run", str(spec), "--trace", str(tr), "--judge", "myjudge:j"]) == 1
    assert cli.main(["run", str(spec), "--trace", str(tr), "--judge", "myjudge:nope"]) == 2


# ---------- HTML ----------
def test_html_report_escapes_and_flags(tmp_path):
    spec = {"name": "<b>x</b>", "selection": {"must_not_call": ["bad"]}}
    trace = T({"tool": "bad", "args": {"q": "<script>alert(1)</script>"}, "result": "ok"})
    html = to_html(run(spec, trace), trace)
    assert "<script>" not in html and "&lt;script&gt;" in html and "&lt;b&gt;x" in html
    assert "FAIL" in html and "class=flag" in html and "<style>" in html and "http" not in html
    out = tmp_path / "r.html"
    tr = tmp_path / "t.jsonl"
    trace.save(str(tr))
    sp = tmp_path / "s.json"
    sp.write_text(json.dumps(spec), encoding="utf-8")
    assert cli.main(["run", str(sp), "--trace", str(tr), "--html", str(out)]) == 1
    assert out.read_text(encoding="utf-8").startswith("<!doctype html>")


# ---------- failure gallery ----------
def test_gallery_not_empty():
    assert len(CASES) >= 10


@pytest.mark.parametrize("path", CASES, ids=[os.path.basename(c)[:-5] for c in CASES])
def test_gallery_case_is_caught(path):
    case = json.load(open(path, encoding="utf-8"))
    trace = Trace.from_jsonl("\n".join(json.dumps(e) for e in case["trace"]))
    rep = run(validate(case["spec"]), trace)
    assert not rep.passed
    assert rep.layers[case["expect_layer"]], f"{case['id']}: lớp {case['expect_layer']} không bắt được"
