# CP2 — Bài 1: agent loop

## Yêu cầu và kết quả

Đã đọc CP2 trong `CHECKPOINTS.md` và contract Bài 1 trong `GUIDE.md`, rồi implement `run_agent(question, provider, tools, max_steps=6)` trong `agent.py`.

Vòng lặp thực hiện:

1. Tạo lịch sử với system prompt và câu hỏi người dùng.
2. Gọi `provider.complete(messages, SCHEMAS)`.
3. Append nguyên vẹn `response['message']` vào lịch sử, lưu usage và sự kiện model.
4. Với từng tool call, parse arguments thành JSON object, gọi `tools.execute`, lưu trace và append tool result dưới dạng JSON string với đúng `tool_call_id`.
5. Sau khi trả đủ mọi tool result, gọi model tiếp với lịch sử đã cập nhật.
6. Chỉ trả `completed` khi `finish == 'stop'` và không còn tool call. Hết số lần gọi model trả `max_steps`; finish bất thường hoặc lỗi kết nối provider trả `error`.

Kết quả luôn có `status`, `answer`, `trace` và `usage`. Một step là một lần gọi model; nhiều tool call trong cùng response cùng thuộc step đó. Arguments không hợp lệ được trả lại model dưới dạng observation `INVALID_ARGUMENTS`; các lỗi dự kiến của tool dùng cơ chế xử lý có sẵn trong `tools.execute`.

## Chạy demo theo checkpoint

```powershell
. .\setup.ps1
python run.py 'GitHub Actions hiện có sự cố không? Hãy kiểm tra incident gần đây.'
```

Đã chạy với API thật, cấu hình `openai` / `gpt-4.1-mini`, tools ở chế độ mặc định `snapshot`. Kết quả đầy đủ được lưu nguyên dạng dict kết quả trong `cp2_demo.json`:

- `status`: **completed**.
- Số lần gọi model: **2**.
- Step 1: model yêu cầu `get_status` với `{"provider": "github", "component": "Actions"}`; Python thực thi và trả JSON về model.
- Step 2: model trả final answer, `finish=stop`, không có tool call.
- Tổng token: **1.023**.
- Tool cho biết Actions là `operational`; năm incident hiển thị đều `resolved`, trong tập có 23 incident khớp.

**Giới hạn quan sát được:** answer demo dùng chữ “Hiện tại” nhưng không nêu rõ thời điểm snapshot `2026-11-09T03:50:47.065020+00:00`. Chỉ có thể kết luận về dữ liệu tại thời điểm snapshot, không xác nhận trạng thái thực tế hôm nay. `completed` chứng minh vòng lặp kết thúc đúng điều kiện, không chứng minh mọi phát biểu trong answer đều chính xác hoặc đầy đủ.

## Câu hỏi: Vì sao phải giữ nguyên assistant message?

Assistant message chứa yêu cầu gọi tool: `tool_calls`, ID, tên tool và JSON arguments, có thể kèm nội dung hoặc metadata của provider. Nó phải đứng trước các tool result trong lịch sử. Nếu chỉ giữ `content`, thông tin model đã yêu cầu tool nào bị mất; provider có thể từ chối lịch sử khi nhận kết quả không có tool call tương ứng. Giữ nguyên message cũng bảo toàn thông tin cần cho model hiểu lượt hội thoại trước.

## Câu hỏi: Vì sao phải trả đúng `tool_call_id` cho mọi call?

`tool_call_id` nối một kết quả với đúng yêu cầu của model; đây là **ID của call**, không phải tên tool. Hai call có thể dùng cùng tên tool nhưng kiểm tra hai provider hoặc hai incident khác nhau. Nếu dùng sai ID, kết quả có thể bị ghép nhầm hoặc API từ chối request. Nếu response có hai call, cần trả đủ hai tool result tương ứng trước lần gọi model tiếp theo; không được dừng sau call đầu tiên.

## Kiểm tra

Đã chạy:

```powershell
python -m unittest discover -s tests -v
```

Kết quả: **37/39 test pass**. Các test vòng lặp, tool result ID, nhiều tool call, trajectory hai tool, giới hạn bước và output bị cắt đều pass. Hai test bổ sung trong `tests/test_cp2.py` kiểm tra assistant message được giữ nguyên trước mọi tool result và usage được lưu cho cả lượt tool lẫn lượt final.

Hai test chưa pass thuộc kiểm tra nguồn ở **Bài 4 / CP5**, chưa nằm trong phần CP2:

- `test_missing_url_gets_revision_within_budget`.
- `test_missing_url_at_budget_limit_is_not_completed`.

Chưa chạy eval trước/sau; các bước đó thuộc CP4 và CP6.
