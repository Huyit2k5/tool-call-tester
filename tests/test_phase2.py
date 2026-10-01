import importlib.util
import json
import os

import pytest

from toolcheck import cli
from toolcheck.checkers import provenance, recovery
from toolcheck.mock import Sandbox, ToolError, replay_tools
from toolcheck.report.junit import to_junit
from toolcheck.runner import run
from toolcheck.trace import Event, Trace

EX = os.path.join(os.path.dirname(__file__), "..", "examples", "reschedule_meeting")


def T(*events):
    return Trace([Event(step=i, **e) for i, e in enumerate(events, 1)])


def load_agent():
    spec = importlib.util.spec_from_file_location("run_agent", os.path.join(EX, "run_agent.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_provenance_invented_id():
    t = T({"tool": "find", "result": {"id": "m1"}}, {"tool": "book", "args": {"id": "m9"}})
    rule = {"rules": [{"tool": "book", "arg": "id", "from_result_of": "find"}]}
    assert len(provenance.check(t, rule)) == 1
    ok = T({"tool": "find", "result": {"id": "m1"}}, {"tool": "book", "args": {"id": "m1"}})
    assert provenance.check(ok, rule) == []


def test_provenance_input_source_and_disallowed():
    t = T({"tool": "book", "args": {"id": "m1"}})
    assert provenance.check(t, {"inputs": ["dời m1"], "rules": [{"tool": "book", "arg": "id"}]}) == []
    strict = {"inputs": ["m1"], "rules": [{"tool": "book", "arg": "id", "from_result_of": "find"}]}
    assert len(provenance.check(t, strict)) == 1


def test_recovery():
    same = T({"tool": "a", "args": {"x": 1}, "error": "400"}, {"tool": "a", "args": {"x": 1}, "result": 1})
    assert any("retry y hệt" in f.message for f in recovery.check(same, {}))
    changed = T({"tool": "a", "args": {"x": 1}, "error": "400"}, {"tool": "a", "args": {"x": 2}, "result": 1})
    assert recovery.check(changed, {}) == []
    dead = T({"tool": "a", "args": {}, "error": "400"})
    assert any("không được phục hồi" in f.message for f in recovery.check(dead, {}))
    assert recovery.check(dead, {"require_recovery": False}) == []
    alt = T({"tool": "a", "error": "x"}, {"tool": "b", "result": 1})
    assert recovery.check(alt, {"alternatives": {"a": ["b"]}}) == []


def test_sandbox_faults_and_replay():
    sb = Sandbox({"t": lambda a, s: {"v": a["n"]}},
                 faults=[{"tool": "t", "on_call": 1, "kind": "timeout"},
                         {"tool": "t", "on_call": 2, "kind": "empty"}])
    with pytest.raises(ToolError, match="timeout"):
        sb.call("t", {"n": 1})
    assert sb.call("t", {"n": 1}) == {}
    assert sb.call("t", {"n": 1}) == {"v": 1}
    assert [e.error for e in sb.trace] == ["timeout", None, None]
    rp = Sandbox(replay_tools(sb.trace))
    with pytest.raises(ToolError, match="timeout"):
        rp.call("t", {"n": 1})
    assert rp.call("t", {"n": 1}) == {}
    with pytest.raises(ToolError, match="replay_miss"):
        rp.call("t", {"n": 2})
    with pytest.raises(ValueError):
        Sandbox({}, faults=[{"tool": "t", "on_call": 1, "kind": "boom"}])


def test_reschedule_good_end_to_end(tmp_path):
    sb = load_agent().run(bad=False)
    spec = json.load(open(os.path.join(EX, "spec.json"), encoding="utf-8"))
    rep = run(spec, sb.trace, sb.state)
    assert rep.passed, rep.to_dict()


def test_reschedule_bad_caught():
    sb = load_agent().run(bad=True)
    spec = json.load(open(os.path.join(EX, "spec.json"), encoding="utf-8"))
    rep = run(spec, sb.trace, sb.state)
    assert rep.layers["provenance"] and rep.layers["recovery"] and rep.layers["final_state"]


def test_cli_junit_and_state(tmp_path):
    sb = load_agent().run(bad=False)
    sb.trace.save(str(tmp_path / "t.jsonl"))
    (tmp_path / "s.json").write_text(json.dumps(sb.state), encoding="utf-8")
    xml = tmp_path / "j.xml"
    code = cli.main(["run", os.path.join(EX, "spec.json"), "--trace", str(tmp_path / "t.jsonl"),
                     "--state", str(tmp_path / "s.json"), "--junit", str(xml)])
    assert code == 0
    assert 'failures="0"' in xml.read_text(encoding="utf-8")


def test_junit_failure_and_missing_state():
    spec = {"name": "n", "final_state": {"equals": {"a": 1}}}
    rep = run(spec, Trace())
    assert not rep.passed
    assert "<failure" in to_junit(rep)
