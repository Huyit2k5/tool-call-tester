# Failure gallery

Các kiểu lỗi tool-call hay gặp. Mỗi case là một file JSON gồm `spec` + `trace` mẫu + lớp checker dự kiến sẽ bắt.
`tests/test_gallery.py` xác nhận mọi case đều bị bắt đúng lớp.

| Case | Lỗi | Lớp bắt | Mô tả |
|---|---|---|---|
| [repeat-same-call](cases/repeat-same-call.json) | Lặp y hệt một lời gọi | `loop` | Agent gọi lại đúng lời gọi cũ dù kết quả không đổi (kể cả khác khoảng trắng/thứ tự khóa). |
| [abab-cycle](cases/abab-cycle.json) | Chu kỳ A→B→A→B | `loop` | Hai tool gọi luân phiên mà không tiến triển. |
| [no-progress](cases/no-progress.json) | Không tiến triển | `loop` | Tham số khác nhau nhưng kết quả giống hệt nhiều bước liền. |
| [invented-id](cases/invented-id.json) | Bịa ID | `provenance` | Tham số id không có trong input hay kết quả tool nào trước đó. |
| [wrong-enum](cases/wrong-enum.json) | Giá trị ngoài enum | `schema` | Tham số không thuộc tập giá trị cho phép. |
| [bad-date-format](cases/bad-date-format.json) | Sai định dạng ngày | `schema` | Agent truyền ngôn ngữ tự nhiên thay vì ISO. |
| [missing-required](cases/missing-required.json) | Thiếu tham số bắt buộc | `schema` | Lời gọi bỏ sót tham số required. |
| [forbidden-tool](cases/forbidden-tool.json) | Gọi tool bị cấm | `selection` | Agent gọi thao tác phá hủy khi chỉ được phép đọc. |
| [missing-required-call](cases/missing-required-call.json) | Quên gọi tool bắt buộc | `selection` | Agent trả lời mà không hề xác minh bằng tool. |
| [wrong-order](cases/wrong-order.json) | Sai thứ tự | `selection` | Thực hiện hành động trước khi kiểm tra. |
| [blind-retry](cases/blind-retry.json) | Retry mù sau lỗi | `recovery` | Sau lỗi 400 agent gọi lại y hệt thay vì sửa tham số. |
| [unrecovered-error](cases/unrecovered-error.json) | Lỗi không được phục hồi | `recovery` | Tool lỗi và agent bỏ cuộc, không thử lại hay đổi hướng. |
| [over-budget](cases/over-budget.json) | Vượt ngân sách | `budget` | Quá nhiều bước/token cho một việc đơn giản. |

Thêm case mới: tạo `cases/<id>.json` cùng cấu trúc (`id`, `title`, `description`, `expect_layer`, `spec`, `trace`); test tự nhận.
