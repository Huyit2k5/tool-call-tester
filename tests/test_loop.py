from toolcheck.checkers import loop
from toolcheck.trace import Event, Trace, call_hash, normalize_args


def mk(*calls, result=None):
    """calls: (tool, args) hoặc (tool, args, result)."""
    events = []
    for i, c in enumerate(calls, 1):
        events.append(Event(step=i, tool=c[0], args=c[1], result=c[2] if len(c) > 2 else i))
    return Trace(events)


def test_empty_and_single():
    assert loop.check(Trace(), {}) == []
    assert loop.check(mk(("a", {})), {}) == []


def test_identical_repeat_caught_at_third():
    f = loop.check(mk(*[("a", {"x": 1})] * 5), {})
    rep = [x for x in f if "lặp y hệt" in x.message]
    assert len(rep) == 1 and rep[0].step == 3


def test_near_identical_normalized():
    t = mk(("a", {"q": "hello  world", "n": 1.0000001}),
           ("a", {"n": 1, "q": " hello world "}),
           ("a", {"q": "hello world", "n": 1.0}))
    assert any("lặp y hệt" in x.message for x in loop.check(t, {}))
    assert call_hash("a", {"b": 1, "a": 2}) == call_hash("a", {"a": 2, "b": 1})


def test_different_valid_args_not_flagged():
    t = mk(*[("a", {"page": i}) for i in range(10)])
    assert loop.check(t, {}) == []


def test_polling_allowed():
    t = mk(*[("status", {"id": 1}, "pending")] * 6)
    assert loop.check(t, {"allow_polling": ["status"]}) == []
    assert loop.check(t, {}) != []


def test_cycle_abab():
    t = mk(("a", {}), ("b", {}), ("a", {}), ("b", {}))
    f = loop.check(t, {"max_repeat_same_call": 99, "max_no_progress": 99})
    assert len(f) == 1 and "a->b" in f[0].message


def test_no_progress():
    t = mk(("a", {"i": 1}, "same"), ("b", {"i": 2}, "same"), ("c", {"i": 3}, "same"))
    assert any("không tiến triển" in x.message for x in loop.check(t, {}))


def test_normalize_stable():
    assert normalize_args({"b": [1.0, " x  y"], "a": None}) == {"a": None, "b": [1, "x y"]}
