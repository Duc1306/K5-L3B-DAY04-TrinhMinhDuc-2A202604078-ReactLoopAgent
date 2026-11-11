# CP3 — Bài 2: xử lý lỗi và trace

## Kết quả

Đã hoàn thiện phần kiểm soát lỗi của `run_agent` theo CP3 trong `CHECKPOINTS.md` và Bài 2 trong `GUIDE.md`:

- Giới hạn bằng `max_steps`: mỗi lần gọi model là một step; hết lượt trả `status=max_steps` và ghi sự kiện cùng tên vào trace.
- Arguments JSON lỗi hoặc không phải object: trả observation `ok=false`, `error=INVALID_ARGUMENTS`, không thực thi tool; model có thể sửa arguments trong lượt sau.
- Tool không tồn tại, provider trong arguments không hợp lệ hoặc timeout: trả observation lỗi từ registry về model và ghi vào trace.
- Nếu `tools.execute` ném exception thay vì trả dict lỗi, agent chuyển exception thành observation và tiếp tục xử lý các tool call còn lại trong response.
- Nếu `provider.complete` ném exception, trả `status=error`, ghi `provider_error` và giữ trace/usage đã có. Bắt exception ở ranh giới gọi provider, bao gồm lỗi định dạng dữ liệu do adapter phát hiện.
- `finish=length`, finish bất thường hoặc `finish=tool_calls` nhưng không có call: trả `status=error`, ghi `model_error`; không thực thi tool từ response bị cắt.
- Giữ nguyên assistant message và trả mọi tool result với đúng `tool_call_id` như CP2.

## Cần hiểu: lỗi nào trả lại model, lỗi nào kết thúc run?

| Tình huống | Xử lý | Lý do |
|---|---|---|
| JSON arguments sai | Trả observation `INVALID_ARGUMENTS` cho model | Model còn có thể sửa cú pháp hoặc kiểu arguments. |
| Tool không tồn tại | Trả observation `UNKNOWN_TOOL` | Model có thể chọn tool có trong schemas. |
| `provider` trong arguments sai | Trả observation lỗi của tool | Model có thể đổi sang `github` hoặc `cloudflare`. |
| Tool timeout hoặc ném exception | Trả observation lỗi, xử lý tiếp các call còn lại | Lỗi lấy dữ liệu không phải trạng thái dịch vụ; model có thể báo chưa đủ dữ liệu hoặc thử lại trong budget. |
| LLM provider lỗi khi gọi model | Kết thúc với `status=error` | Chưa có response hợp lệ để tiếp tục; không tự retry vô hạn. |
| `finish=length` hoặc finish bất thường | Kết thúc với `status=error` | Output chưa hoàn chỉnh, không được coi là final answer. |
| Hết `max_steps` | Kết thúc với `status=max_steps` | Chặn vòng lặp và giới hạn số lần gọi model. |

Lỗi tool không đồng nghĩa toàn bộ run phải mang status `error`. Agent vẫn có thể `completed` nếu model kết thúc bằng câu trả lời nêu rõ phần chưa kiểm tra được. `completed` mô tả cách vòng lặp kết thúc, không bảo đảm nội dung câu trả lời đúng.

## Trace để debug

Tool event giữ đủ các key mà tests và eval đọc: `event`, `step`, `name`, `arguments`, `result`. Bổ sung `tool_call_id` để ghép đúng call và `raw_arguments` để đối chiếu JSON ban đầu, kể cả khi parse thất bại.

Ví dụ thật từ demo offline `invalid_arguments` trong `cp3_demo.json`:

```json
{
  "event": "tool",
  "step": 1,
  "name": "get_status",
  "tool_call_id": "bad-json",
  "raw_arguments": "{",
  "arguments": "{",
  "result": {
    "ok": false,
    "error": "INVALID_ARGUMENTS",
    "message": "Arguments phải là JSON object hợp lệ."
  }
}
```

Các sự kiện khác: `model` lưu step và finish; `provider_error`/`model_error` lưu lý do lỗi; `max_steps` đánh dấu hết lượt. Trace không ghi API key, đối tượng provider hay nội dung suy nghĩ của model.

## Kiểm tra và demo

Đã chạy:

```powershell
python -m unittest discover -s tests -v
```

Kết quả: **45/47 test pass**, gồm **8 test CP3 mới** trong `tests/test_cp3.py` (một số test chạy nhiều tình huống bằng `subTest`). Chỉ còn hai test của Bài 4 / CP5:

- `test_missing_url_gets_revision_within_budget`.
- `test_missing_url_at_budget_limit_is_not_completed`.

Đây là trạng thái đúng với mục tự kiểm tra CP3. Chưa triển khai kiểm tra bắt buộc URL nguồn của CP5.

`cp3_demo.json` lưu kết quả chạy offline với fake provider có response được lập sẵn:

| Demo | Status | Các sự kiện |
|---|---|---|
| `invalid_arguments` | `completed` | `model → tool (INVALID_ARGUMENTS) → model` |
| `tool_timeout` | `completed` | `model → tool (TimeoutError) → model` |
| `provider_error` | `error` | `provider_error` |
| `truncated_output` | `error` | `model → model_error` |
| `max_steps` | `max_steps` | `model → tool → max_steps` |

Demo và unit tests không gọi LLM thật, không tiêu tốn token và không đánh giá khả năng model tự xử lý lỗi ngoài thực tế. Bài eval với model thật thuộc CP4.
