# Viết checker riêng (plugin)

Một checker là hàm `fn(trace, cfg) -> list[Finding]`. Rỗng nghĩa là pass.

## 1. Viết (5 phút)

```python
# my_checker.py
from toolcheck.checkers import Finding
from toolcheck.plugins import register

@register("no_empty_query")
def check(trace, cfg):
    return [Finding("no_empty_query", "query rỗng", e.step)
            for e in trace if e.tool == "search" and not e.args.get("q")]
```

- `trace` lặp được thành các `Event` (`step`, `tool`, `args`, `result`, `error`, `ts`, `tokens`).
- `cfg` là object bạn khai trong spec. Tự kiểm tra `cfg` và `raise ValueError("...")` nếu sai; CLI báo lỗi rõ và thoát mã 2.
- `Finding(layer, message, step=None)`; `step` giúp báo cáo HTML tô sáng đúng dòng.
- Tên không được trùng checker có sẵn (`selection`, `schema`, `provenance`, `loop`, `recovery`, `budget`).

## 2. Dùng trong spec

```json
{"name": "demo", "checks": {"no_empty_query": {}}}
```

```bash
toolcheck run spec.json --trace trace.jsonl --plugin my_checker
```

`--plugin` import module (lặp được nhiều lần). Module phải nằm trong `PYTHONPATH`/thư mục hiện tại.

## 3. Phát hành như gói (tùy chọn)

Khai entry point để người dùng khỏi gõ `--plugin`:

```toml
[project.entry-points."toolcheck.checkers"]
no_empty_query = "my_pkg.checks:check"
```

## 4. Kiểm thử checker của bạn

```python
from toolcheck.trace import Trace
from my_checker import check

def test_flags_empty():
    t = Trace.from_jsonl('{"tool": "search", "args": {"q": ""}}')
    assert check(t, {})
```

Ví dụ chạy được: `examples/plugin_demo/`.

## Plugin `semantic_args` (LLM judge)

Có sẵn nhưng **không bật mặc định** và không gắn SDK nào: bạn truyền hàm judge `prompt -> str|dict`.

```python
from toolcheck.plugins_semantic import set_judge
set_judge(lambda prompt: call_my_llm(prompt))   # trả {"ok": bool, "reason": str} hoặc "PASS ..."/"FAIL ..."
```

```bash
toolcheck run spec.json --trace trace.jsonl --judge my_judges:claude_judge
```

```json
{"checks": {"semantic_args": {
  "task": "Dời họp sprint sang chiều thứ Sáu",
  "rules": [{"tool": "reschedule_meeting", "criterion": "slot phải là chiều thứ Sáu"}]}}}
```

Lưu ý:
- Judge nhận tác vụ, lịch sử tool trước đó và lời gọi cần chấm. **Dữ liệu này rời máy bạn nếu judge gọi API ngoài**; che khóa/PII trước khi chạy.
- Kết quả LLM không xác định trước. Dùng cho kiểm tra ngữ nghĩa mà checker xác định không làm được, không thay thế chúng.
- Judge trả về định dạng không hiểu được sẽ thành một finding, không bị bỏ qua âm thầm.
- Thiếu judge thì chạy báo lỗi (mã 2), không tự pass.
