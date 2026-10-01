import asyncio
import json

import pytest

from toolcheck import cli
from toolcheck.adapters import convert, otel
from toolcheck.guard import BudgetExceeded, LoopDetected, LoopGuard
from toolcheck.trace import Trace


# ---------- guard ----------
def test_guard_blocks_before_calling_fn():
    calls = []
    g = LoopGuard(max_repeat=3)
    fn = lambda **a: calls.append(a) or {"n": len(calls)}  # kết quả khác nhau mỗi lần
    g.call("s", {"q": 1}, fn)
    g.call("s", {"q": 1}, fn)
    with pytest.raises(LoopDetected) as ei:
        g.call("s", {"q": 1}, fn)
    assert len(calls) == 2 and ei.value.step == 3 and len(g.trace) == 2


def test_guard_allows_different_args_and_polling():
    g = LoopGuard(max_repeat=3, allow_polling=["status"])
    for i in range(10):
        g.call("s", {"page": i}, lambda **a: {"p": a["page"]})
    for _ in range(6):
        g.call("status", {"id": 1}, lambda **a: {"state": "pending"})


def test_guard_cycle_and_no_progress_after_call():
    g = LoopGuard(max_repeat=99, max_no_progress=99)
    f = lambda **a: a
    g.call("a", {}, f); g.call("b", {}, f); g.call("a", {}, f)
    with pytest.raises(LoopDetected, match="a->b"):
        g.call("b", {}, f)
    g2 = LoopGuard(max_repeat=99)
    same = lambda **a: "same"
    g2.call("a", {"i": 1}, same); g2.call("b", {"i": 2}, same)
    with pytest.raises(LoopDetected, match="không tiến triển") as ei:
        g2.call("c", {"i": 3}, same)
    assert ei.value.result == "same" and len(g2.trace) == 3


def test_guard_budget():
    g = LoopGuard(max_steps=2)
    g.call("a", {"i": 1}, lambda **a: 1); g.call("a", {"i": 2}, lambda **a: 2)
    with pytest.raises(BudgetExceeded):
        g.call("a", {"i": 3}, lambda **a: 3)
    g = LoopGuard(max_tokens=100)
    with pytest.raises(BudgetExceeded):
        g.call("a", {"i": 1}, lambda **a: 1, tokens=150)
    now = [0.0]
    g = LoopGuard(max_seconds=10, clock=lambda: now[0])
    g.call("a", {"i": 1}, lambda **a: 1)
    now[0] = 100.0
    with pytest.raises(BudgetExceeded, match="quá"):
        g.call("a", {"i": 2}, lambda **a: 2)


def test_guard_records_error_and_reraises():
    g = LoopGuard()
    def boom(**a):
        raise RuntimeError("400 bad")
    with pytest.raises(RuntimeError):
        g.call("a", {}, boom)
    assert g.trace.events[0].error == "400 bad"


def test_guard_async():
    async def fn(**a):
        return {"ok": a["i"]}
    g = LoopGuard(max_repeat=2)
    async def go():
        await g.acall("a", {"i": 1}, fn)
        await g.acall("a", {"i": 1}, fn)
    with pytest.raises(LoopDetected):
        asyncio.run(go())


# ---------- adapters ----------
OPENAI_CHAT = [
    {"role": "user", "content": "x"},
    {"role": "assistant", "usage": {"total_tokens": 120}, "tool_calls": [
        {"id": "c1", "function": {"name": "find", "arguments": "{\"q\": \"a\"}"}},
        {"id": "c2", "function": {"name": "other", "arguments": "{}"}}]},
    {"role": "tool", "tool_call_id": "c1", "content": "{\"id\": \"m1\"}"},
    {"role": "tool", "tool_call_id": "c2", "content": "{\"error\": \"404\"}"},
]


def test_openai_chat():
    t = convert("openai", OPENAI_CHAT)
    assert [e.tool for e in t] == ["find", "other"]
    assert t.events[0].args == {"q": "a"} and t.events[0].result == {"id": "m1"}
    assert t.events[0].tokens == 120 and t.events[1].tokens == 0
    assert t.events[1].error == "404"


def test_openai_responses():
    t = convert("openai", {"output": [
        {"type": "function_call", "call_id": "k", "name": "f", "arguments": "{\"a\": 1}"},
        {"type": "function_call_output", "call_id": "k", "output": "plain text"}]})
    assert t.events[0].args == {"a": 1} and t.events[0].result == "plain text"


def test_anthropic():
    msgs = [
        {"role": "assistant", "usage": {"input_tokens": 100, "output_tokens": 20}, "content": [
            {"type": "text", "text": "ok"},
            {"type": "tool_use", "id": "t1", "name": "find", "input": {"q": "a"}},
            {"type": "tool_use", "id": "t2", "name": "bad", "input": {}}]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": [{"type": "text", "text": "{\"id\": 7}"}]},
            {"type": "tool_result", "tool_use_id": "t2", "is_error": True, "content": "boom"}]},
    ]
    t = convert("anthropic", msgs)
    assert t.events[0].result == {"id": 7} and t.events[0].tokens == 120
    assert t.events[1].error == "boom" and t.events[1].result is None


def test_mcp():
    log = [
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "f", "arguments": {"a": 1}}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "g", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 2, "error": {"code": -32000, "message": "timeout"}},
        {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "{\"x\": 1}"}], "isError": False}},
    ]
    t = convert("mcp", log)
    assert t.events[0].result == {"x": 1} and t.events[1].error == "timeout"
    t2 = convert("mcp", [log[0], {"id": 1, "result": {"isError": True, "content": [{"type": "text", "text": "nope"}]}}])
    assert t2.events[0].error == "nope"


def test_otel_roundtrip_and_otlp_attrs():
    t = convert("openai", OPENAI_CHAT)
    for i, e in enumerate(t.events):
        e.ts = 100.0 + i
    back = otel.to_trace(otel.to_spans(t))
    assert [(e.tool, e.args, e.result, e.error) for e in back] == [(e.tool, e.args, e.result, e.error) for e in t]
    otlp = [{"name": "execute_tool x", "start_time_unix_nano": 5, "attributes": [
        {"key": "gen_ai.tool.name", "value": {"stringValue": "x"}},
        {"key": "gen_ai.tool.call.arguments", "value": {"stringValue": "{\"k\": 1}"}}]}]
    assert otel.to_trace(otlp).events[0].args == {"k": 1}


def test_unknown_adapter():
    with pytest.raises(ValueError, match="không có"):
        convert("nope", [])


def test_cli_convert_and_run_format(tmp_path):
    src = tmp_path / "chat.json"
    src.write_text(json.dumps(OPENAI_CHAT), encoding="utf-8")
    out = tmp_path / "t.jsonl"
    assert cli.main(["convert", str(src), "--from", "openai", "-o", str(out)]) == 0
    assert len(Trace.load(str(out))) == 2
    spec = tmp_path / "s.json"
    spec.write_text(json.dumps({"selection": {"must_call": ["find"]}}), encoding="utf-8")
    assert cli.main(["run", str(spec), "--trace", str(src), "--format", "openai"]) == 0
    assert cli.main(["convert", str(tmp_path / "missing.json"), "--from", "mcp", "-o", str(out)]) == 2


# ---------- final_answer & recovery (phát hiện từ model thật) ----------
def test_final_answer_extracted_and_roundtrips(tmp_path):
    chat = OPENAI_CHAT + [{"role": "assistant", "content": "Xin lỗi, giờ đó đã kín. Chọn giờ khác nhé?"}]
    t = convert("openai", chat)
    assert t.final_answer.startswith("Xin lỗi")
    p = tmp_path / "t.jsonl"
    t.save(str(p))
    assert Trace.load(str(p)).final_answer == t.final_answer
    assert convert("openai", OPENAI_CHAT).final_answer is None
    an = convert("anthropic", [{"role": "assistant", "content": [{"type": "text", "text": "xong"}]}])
    assert an.final_answer == "xong"


def test_recovery_accepts_escalation_only_when_last_and_enabled():
    from toolcheck.checkers import recovery
    from toolcheck.trace import Event
    err = Event(step=1, tool="a", args={"x": 1}, error="400")
    assert recovery.check(Trace([err]), {})  # không có câu trả lời cuối -> vẫn báo
    assert recovery.check(Trace([err], "Chọn giờ khác nhé?"), {}) == []
    assert recovery.check(Trace([err], "Chọn giờ khác nhé?"), {"accept_final_answer": False})
    later = [err, Event(step=2, tool="b", args={}, result=1)]
    assert recovery.check(Trace(later, "xong"), {})  # lỗi không phải lời gọi cuối
