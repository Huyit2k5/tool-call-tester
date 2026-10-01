# Kế hoạch thực hiện: Tool-call Tester (open-source)

> Tên tạm: `toolcheck` (kiểm tra trùng tên trên PyPI/GitHub trước khi chốt)
> Mô tả một câu: *pytest cho tool-call của agent: chạy offline, không cần tài khoản, bắt lỗi chọn tool, sai tham số, vòng lặp vô hạn.*

---

## 1. Mục tiêu và phạm vi

### Mục tiêu
- Phát hành bản open-source dùng được thật, cài bằng `pip install` và chạy trong 3 dòng lệnh.
- Bắt được các lỗi tool-call phổ biến mà không cần gọi LLM.
- Có runtime guard để chặn vòng lặp ngay khi agent đang chạy.

### Trong phạm vi
- Định dạng trace chuẩn (JSONL).
- Test spec (YAML/JSON) mô tả hợp đồng của từng tình huống.
- Checker xác định: selection, schema, loop, budget, provenance, recovery.
- Mock/replay tool, chèn lỗi (fault injection).
- CLI, báo cáo terminal/JSON/JUnit.
- Adapter cho OpenAI, Anthropic, MCP (gói phụ, tùy chọn).

### Ngoài phạm vi (không làm, để tránh đối đầu nền tảng eval lớn)
- Dashboard web, lưu trữ trace trên cloud.
- Bộ metric tổng quát cho chất lượng câu trả lời.
- Huấn luyện/fine-tune model.

### Nguyên tắc
1. Lõi zero-dependency (chỉ thư viện chuẩn Python).
2. Test theo hợp đồng, không ép một trace cố định.
3. Xác định trước, LLM sau (LLM judge chỉ là plugin tùy chọn).
4. Dữ liệu ở lại máy người dùng.

---

## 2. Tổng quan lộ trình

| Giai đoạn | Thời gian | Kết quả chính |
|---|---|---|
| Giai đoạn 0: Chuẩn bị | Tuần 0 | Repo, tên, giấy phép, khung dự án |
| Giai đoạn 1: v0.1 (MVP) | Tuần 1-3 | Trace + loop + budget + selection + schema + CLI |
| Giai đoạn 2: v0.2 | Tuần 4-5 | Mock/replay, provenance, recovery, fault injection, JUnit |
| Giai đoạn 3: v0.3 | Tuần 6-8 | Adapter OpenAI/Anthropic/MCP, runtime guard |
| Giai đoạn 4: v0.4 | Tuần 9-10 | LLM judge plugin, báo cáo HTML |
| Giai đoạn 5: v1.0 | Tuần 11-12 | Ổn định spec/trace, tài liệu đầy đủ, ra mắt chính thức |

Ước lượng dựa trên làm một mình, bán thời gian. Điều chỉnh theo thời gian thực tế.

---

## 3. Giai đoạn 0: Chuẩn bị (Tuần 0)

- [ ] Chốt tên, kiểm tra trùng trên PyPI, GitHub, tên miền.
- [ ] Tạo repo GitHub, chọn giấy phép (MIT hoặc Apache-2.0).
- [x] Dựng cấu trúc thư mục:
  ```
  toolcheck/
  ├─ src/toolcheck/
  │  ├─ trace.py
  │  ├─ spec.py
  │  ├─ runner.py
  │  ├─ guard.py
  │  ├─ checkers/
  │  └─ report/
  ├─ adapters/
  ├─ examples/
  ├─ docs/
  ├─ tests/
  ├─ CONTRIBUTING.md
  ├─ README.md
  └─ LICENSE
  ```
- [x] Cấu hình `pyproject.toml` (không khai báo dependency ở lõi).
- [x] Thiết lập CI cơ bản (chạy test trên nhiều phiên bản Python).
- [x] Viết `README` khung: vấn đề, cách cài, ví dụ 3 dòng.

**Tiêu chí hoàn thành:** `pip install -e .` chạy được, CI xanh với một test rỗng.

---

## 4. Giai đoạn 1: v0.1, MVP (Tuần 1-3)

### 4.1 Trace chuẩn (`trace.py`)
- [x] Định nghĩa sự kiện: `step`, `tool`, `args`, `result`, `error`, `ts`, `tokens`.
- [x] Đọc/ghi JSONL.
- [x] Hàm chuẩn hóa tham số (sắp xếp khóa, bỏ khoảng trắng thừa, làm tròn số) để băm ổn định.

### 4.2 Checker `loop` (ưu tiên số 1, là điểm khác biệt)
- [x] Phát hiện lặp y hệt: băm (tên tool + tham số đã chuẩn hóa), đếm số lần.
- [x] Phát hiện chu kỳ A→B→A→B (kiểm tra chuỗi lặp theo cửa sổ trượt).
- [x] Phát hiện "không tiến triển": nhiều bước liên tiếp kết quả giống nhau.
- [x] Ngưỡng cấu hình được: `max_repeat_same_call`, độ dài chu kỳ tối đa.

**Các trường hợp biên cần test:**
- Lặp gần giống (chỉ khác khoảng trắng, thứ tự khóa, số thực làm tròn).
- Gọi lại cùng tool nhưng tham số hợp lệ khác nhau (không được báo lặp oan).
- Polling hợp lệ (gọi lại để chờ trạng thái đổi) cần cho phép cấu hình ngoại lệ.
- Trace rỗng, trace chỉ có một bước.

### 4.3 Checker `budget`
- [x] Giới hạn số bước, tổng token, tổng thời gian.

### 4.4 Checker `selection` và `schema`
- [x] `must_call`, `must_not_call`, `order` (tùy chọn).
- [x] Kiểm tra tham số theo schema đơn giản tự viết (kiểu, bắt buộc, enum, định dạng ISO), không dùng thư viện ngoài.

### 4.5 Test spec (`spec.py`)
- [x] Định dạng JSON trước (thuần, không cần thư viện). YAML để giai đoạn sau, vì YAML cần parser ngoài.
- [x] Kiểm tra spec hợp lệ, báo lỗi rõ dòng nào sai.

### 4.6 CLI và báo cáo
- [x] `toolcheck run spec.json --trace trace.jsonl`
- [x] Báo cáo terminal theo từng lớp (selection/schema/loop/budget), pass/fail rõ ràng.
- [x] Mã thoát khác 0 khi fail.
- [x] Xuất JSON.

### 4.7 Demo và tài liệu
- [x] Demo "vòng lặp đốt tiền": agent giả lặp 40 lần, `toolcheck` bắt ở lần thứ 3, in ra số token tiết kiệm được.
- [ ] Ghi GIF terminal cho README.
- [x] 3 ví dụ chạy ngay trong `examples/`.

**Tiêu chí hoàn thành v0.1:**
- Người lạ làm theo README chạy được demo trong dưới 5 phút.
- Bộ test đơn vị phủ các checker chính, gồm các trường hợp biên ở 4.2.
- Phát hành lên PyPI và gắn tag `v0.1.0`.

---

## 5. Giai đoạn 2: v0.2 (Tuần 4-5)

- [x] **Mock/replay tool**: ghi lại phản hồi thật, phát lại khi test; tool giả trả dữ liệu cố định.
- [x] **Checker `provenance`**: giá trị tham số phải có nguồn từ input hoặc kết quả tool trước (bắt lỗi "bịa ID"). Cú pháp `from_result_of`.
- [x] **Checker `recovery`**: sau lỗi, agent có đổi tham số/chiến lược không, hay retry y hệt.
- [x] **Fault injection**: chèn lỗi (400, timeout, dữ liệu rỗng) vào lần gọi chỉ định.
- [x] **Báo cáo JUnit XML** để tích hợp CI.
- [x] Hỗ trợ YAML (tùy chọn, thêm như extra để lõi vẫn zero-dependency).
- [x] Kiểm tra trạng thái cuối (`final_state`) với tool giả lập có trạng thái đơn giản.

**Tiêu chí hoàn thành:** chạy được toàn bộ ví dụ "dời lịch họp" (chọn tool, tham số, lỗi 400, phục hồi) trong CI.

---

## 6. Giai đoạn 3: v0.3 (Tuần 6-8)

- [x] **Adapter** (gói phụ `toolcheck[openai]`, `toolcheck[anthropic]`, `toolcheck[mcp]`): chuyển log/SDK của từng nền tảng về trace chuẩn.
- [x] **Runtime guard** (`guard.py`): wrapper bọc hàm gọi tool, raise `LoopDetected`/`BudgetExceeded` khi vượt ngưỡng.
  ```python
  guard = LoopGuard(max_repeat=3, max_steps=20)
  result = guard.call(tool_name, args, fn)
  ```
- [x] Kiểm tra tương thích với định dạng trace của OpenTelemetry, cân nhắc xuất/nhập để tránh tự đặt chuẩn riêng.
- [x] Ví dụ tích hợp thực tế với mỗi adapter.

**Tiêu chí hoàn thành:** một agent thật (dùng API thật) bị chặn vòng lặp bởi guard; adapter có test riêng.

---

## 7. Giai đoạn 4: v0.4 (Tuần 9-10)

- [x] **Plugin `semantic_args`** dùng LLM judge (tùy chọn, không bật mặc định).
- [x] Giao diện plugin rõ ràng để cộng đồng viết checker riêng.
- [x] **Báo cáo HTML** tĩnh một file, không cần server.
- [x] `failure-gallery/`: thư viện các kiểu lỗi tool-call hay gặp, mỗi kiểu có test mẫu.

**Tiêu chí hoàn thành:** viết được một checker tùy chỉnh theo tài liệu plugin trong dưới 30 phút.

---

## 8. Giai đoạn 5: v1.0 (Tuần 11-12)

- [ ] Đóng băng định dạng spec và trace, cam kết tương thích ngược.
- [ ] Tài liệu đầy đủ: bắt đầu nhanh, tham chiếu spec, viết adapter, viết checker, FAQ.
- [ ] `CONTRIBUTING.md`, mẫu issue/PR, quy tắc ứng xử.
- [ ] Gắn nhãn `good first issue` cho việc nhỏ (adapter mới, checker nhỏ, ví dụ).
- [ ] Rà soát bảo mật: trace không chứa khóa API, hướng dẫn che dữ liệu nhạy cảm.

**Tiêu chí hoàn thành:** tag `v1.0.0`, tài liệu hoàn chỉnh, ít nhất vài người ngoài dùng thử và phản hồi.

---

## 9. Kế hoạch ra mắt và thu hút người dùng

| Việc | Thời điểm |
|---|---|
| README có GIF và demo "vòng lặp đốt tiền" | Trước v0.1 |
| Bài blog kể một lỗi thật mà công cụ bắt được | Khi ra v0.1 |
| Đăng Hacker News, Reddit (r/LocalLLaMA, r/MachineLearning) | Khi ra v0.1 hoặc v0.3 |
| Đăng cộng đồng MCP và nhóm AI Engineer Việt Nam | Khi ra v0.3 |
| Bài so sánh "khi nào dùng toolcheck, khi nào dùng nền tảng eval lớn" | Khi ra v1.0 |

Chỉ số theo dõi: số sao GitHub, lượt tải PyPI, số issue/PR từ người ngoài, số adapter do cộng đồng đóng góp.

---

## 10. Rủi ro và cách giảm

| Rủi ro | Mức | Cách giảm |
|---|---|---|
| Trùng công cụ có sẵn (DeepEval, Confident AI...) | Cao | Giữ trọng tâm loop guard, side-effect, nhẹ/offline; không mở rộng thành nền tảng tổng quát |
| Báo lặp oan (polling hợp lệ) | Trung bình | Ngưỡng cấu hình, danh sách ngoại lệ, test các trường hợp biên |
| Định dạng trace phân mảnh | Trung bình | Adapter tách riêng, cân nhắc tương thích OpenTelemetry |
| Khó duy trì một mình | Trung bình | Giữ lõi nhỏ, để cộng đồng lo adapter, nhãn `good first issue` |
| Không ai dùng | Trung bình | Dùng nội bộ ở công ty trước để có dữ liệu lỗi thật; ra v0.1 sớm lấy phản hồi |
| Rò dữ liệu nhạy cảm trong trace | Thấp-Trung bình | Mặc định không gửi dữ liệu đi đâu, hướng dẫn che thông tin |

---

## 11. Việc làm ngay tuần này

1. Chốt tên và tạo repo.
2. Viết `trace.py` (định dạng trace + chuẩn hóa tham số).
3. Viết checker `loop` kèm các test trường hợp biên.
4. Dựng demo agent bị lặp.

Khi xong 4 việc này là đã có thể đăng bản v0.1 sơ khai để lấy phản hồi.

---

## 12. Quyết định còn bỏ ngỏ

- [ ] Tên dự án cuối cùng.
- [ ] MIT hay Apache-2.0.
- [ ] Hỗ trợ YAML từ v0.1 hay để v0.2.
- [ ] Có xuất/nhập OpenTelemetry ngay từ v0.3 hay để sau.
