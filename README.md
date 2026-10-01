# toolcheck

pytest cho tool-call của agent: chạy offline, không cần tài khoản, bắt lỗi chọn tool, sai tham số và vòng lặp vô hạn. Lõi không có dependency ngoài.

## Cài và chạy (3 dòng)

```bash
pip install -e .
python examples/burn_money_loop/make_trace.py
toolcheck run examples/burn_money_loop/spec.json --trace examples/burn_money_loop/trace.jsonl
```

Demo "vòng lặp đốt tiền": agent giả gọi `search_flights` y hệt 40 lần. `toolcheck` bắt ở lần thứ 3 và in số token có thể tiết kiệm. Mã thoát khác 0 khi fail.

## Trace (JSONL)

Mỗi dòng một lời gọi: `step`, `tool`, `args`, `result`, `error`, `ts`, `tokens`.

## Spec (JSON)

| Khóa | Nội dung |
|---|---|
| `selection` | `must_call`, `must_not_call`, `order` |
| `schema.tools.<tool>` | `required`, `properties` (`type`, `enum`, `format`: `iso-date`/`iso-datetime`), `additional_properties` |
| `loop` | `max_repeat_same_call`, `max_cycle_len`, `min_cycle_repeats`, `max_no_progress`, `allow_polling` |
| `provenance` | `inputs`, `rules`: `{tool, arg, from_result_of, allow_input}` (bắt lỗi bịa ID) |
| `recovery` | `max_identical_retries`, `require_recovery`, `alternatives` |
| `final_state` | `equals`: so khớp tập con với state cuối (`--state state.json`) |
| `budget` | `max_steps`, `max_tokens`, `max_seconds` |

Báo cáo: `--json out.json`, `--junit out.xml` (cho CI). Spec YAML: `pip install toolcheck[yaml]`, dùng đuôi `.yaml`.

## Mock, replay, chèn lỗi

`toolcheck.mock.Sandbox` chạy tool giả, tự ghi trace, chèn lỗi (`error`/`timeout`/`empty`) vào lần gọi chỉ định; `replay_tools(trace)` phát lại phản hồi đã ghi. Xem `examples/reschedule_meeting/` (chạy `run_agent.py` hoặc `run_agent.py --bad`). Xem thêm 3 ví dụ trong `examples/`.

## Adapter và runtime guard

Chuyển log nền tảng về trace chuẩn (không cần cài SDK):

```bash
toolcheck convert chat.json --from openai -o trace.jsonl      # openai | anthropic | mcp | otel
toolcheck run spec.json --trace messages.json --format anthropic
```

`toolcheck.adapters.otel.to_spans(trace)` xuất span theo GenAI semantic conventions (`gen_ai.tool.*`); `--from otel` nhập lại.

Chặn vòng lặp ngay khi agent đang chạy:

```python
from toolcheck.guard import LoopGuard, LoopDetected, BudgetExceeded
guard = LoopGuard(max_repeat=3, max_steps=20)
result = guard.call(tool_name, args, fn)   # raise trước khi gọi fn nếu lặp; có acall cho async
```

Ví dụ: `examples/guard_demo/` (`offline_agent.py` chạy ngay; `anthropic_agent.py`, `openai_agent.py` dùng API thật).

## Plugin, LLM judge, báo cáo HTML, failure gallery

- Viết checker riêng bằng `@register` và khai trong spec ở khóa `checks`; xem [docs/plugins.md](docs/plugins.md) và `examples/plugin_demo/`.
- `semantic_args`: kiểm ngữ nghĩa tham số bằng LLM judge do bạn truyền vào (tùy chọn, không bật mặc định, không gắn SDK).
- `--html report.html`: báo cáo tĩnh một file, tô sáng các bước lỗi.
- [failure-gallery/](failure-gallery/README.md): các kiểu lỗi tool-call hay gặp, mỗi kiểu có test mẫu.

## Trạng thái

v0.4. Xem [ke-hoach-toolcheck.md](ke-hoach-toolcheck.md) cho lộ trình.

MIT License.
