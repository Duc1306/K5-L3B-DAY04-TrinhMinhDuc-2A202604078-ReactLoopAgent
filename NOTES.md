# Ghi chú phân tích · Day 04

Họ và tên: Trịnh Minh Đức
MSSV: 2A202604078

## 1. Case được chọn

- ID case: **H6**, scenario `noisy_status`, trong `eval_before.json` của CP4.
- Câu hỏi: xem status GitHub Actions, đọc incident `h02n9572mx9y` rồi theo liên kết của nó để tìm nguyên nhân, nêu giới hạn dữ liệu và dẫn nguồn.
- Lỗi chọn để sửa ở CP5: final answer không chứa URL incident mà `get_incident_details` đã trả thành công; model tự viết lại URL thay vì dùng nguyên nguồn đã quan sát.
- Điểm lần 1: **60/100**, điểm thô của judge **96**, bị áp trần 60 do chỉ có tool calls ở một model step. Lỗi thiếu URL quan sát được là lỗi xác định khi đọc answer/trace; không phải nguyên nhân trực tiếp của trần điểm này.

Trích nguyên văn phần nguồn của answer trước cải tiến:

```text
Nguồn dữ liệu:
- https://www.githubstatus.com/incidents/h02n9572mx9y
- https://www.githubstatus.com/incidents/xr3myzjms51
```

URL `https://stspg.io/7pwv28hvkmz8` do tool trả về không xuất hiện trong answer. URL thứ hai còn thiếu ký tự `7` trong ID: ID được update dẫn tới là `xr3myzj7ms51`, không phải `xr3myzjms51`.

## 2. Bằng chứng trong trace

Trích rút gọn các trường liên quan từ `cases[id=H6].result.trace` trong `eval_before.json`; phần updates dưới đây chỉ hiển thị update chứa liên kết:

```json
{
  "event": "tool",
  "step": 1,
  "name": "get_incident_details",
  "arguments": {
    "provider": "github",
    "incident_id": "h02n9572mx9y"
  },
  "result": {
    "ok": true,
    "id": "h02n9572mx9y",
    "url": "https://stspg.io/7pwv28hvkmz8",
    "updates_total": 4,
    "updates": [
      {
        "status": "resolved",
        "created_at": "2026-11-04T18:16:08.361Z",
        "body": "Please refer to the combined summary in this related incident: https://www.githubstatus.com/incidents/xr3myzj7ms51",
        "truncated": false
      }
    ]
  }
}
```

Sau kết quả tool, model kết thúc ngay ở step 2:

```json
{"event": "model", "step": 2, "finish": "stop"}
```

**Nguyên nhân ở loop:** trước CP5, nhánh `finish == 'stop'` chấp nhận answer ngay khi không còn tool call; không kiểm tra answer có dẫn URL incident đã quan sát không. System prompt đã yêu cầu dẫn nguồn, nhưng chỉ nhắc bằng prompt chưa đủ để phát hiện việc model viết lại hoặc bỏ URL.

**Không phải thiếu dữ liệu nguồn:** tool đã trả `ok=true` và URL cụ thể. Incident liên quan cũng đọc được trong case A6 của cùng bộ eval. H6 chưa đọc incident đó là lỗi điều tra riêng; không thể nói công cụ không có dữ liệu.

Trace H6 còn cho thấy agent chỉ dùng 2/8 model calls, nên việc dừng sớm không phải do hết budget. Bước kiểm tra nguồn dưới đây xử lý phần thiếu URL đã quan sát; chưa chứng minh xử lý được lỗi theo liên kết, sai thời gian, hay các khẳng định khác trong answer.

## 3. Thay đổi đã thực hiện

- Sửa trong `agent.py`: thêm bước kiểm tra sự hiện diện URL incident trước khi trả `completed`, theo hướng dẫn Bài 4 trong `GUIDE.md`.
- Mỗi run có một tập URL riêng. Chỉ lưu URL dạng string không rỗng từ `get_incident_details` trả thành công; không lấy URL của tool thất bại hay chỉ lấy nguồn tổng quan của `get_status`.
- Nếu có URL đã quan sát nhưng final answer không chứa URL nào trong tập đó, ghi event `validation_missing_source`, kèm step, danh sách URL và candidate answer bị từ chối vào trace.
- Giữ nguyên assistant message rồi thêm yêu cầu sửa vào lịch sử để model sao chép ít nhất một URL đã quan sát. Lượt sửa vẫn tính trong `max_steps` và usage; không mở một vòng retry ngoài budget.
- Nếu model tiếp tục thiếu nguồn đến hết budget, trả `max_steps`, không báo `completed` và không trả candidate bị từ chối làm final answer.
- Nếu không đọc thành công incident có URL, không ép model thêm link. Giữ nguyên system prompt để phạm vi thay đổi tập trung vào bước kiểm tra trong loop; ID và URL không được hard-code trong agent.

**Vì sao chọn:** H6 có bằng chứng nguồn cụ thể đã tồn tại nhưng không được dùng. Kiểm tra này có điều kiện rõ, kiểm thử được và hoàn thành contract trong `tests/test_validation.py`. Nó không yêu cầu sửa fixtures, expected hay cách chấm điểm.

### Kiểm tra offline

Đã chạy `python -m unittest discover -s tests -v`: **54/54 test pass**. Hai test kiểm tra nguồn trước đây thất bại nay đều pass. Thêm 7 test trong `tests/test_cp5.py` cho các trường hợp:

- Yêu cầu sửa giữ nguyên lịch sử, tool call ID và usage.
- Answer có URL đã quan sát thì được chấp nhận ngay.
- Link trang tổng quan không thay thế được URL incident đã đọc.
- Lặp lại thiếu nguồn vẫn bị giới hạn bởi budget.
- Chỉ kiểm tra status thì không bắt buộc URL incident.
- URL đi kèm kết quả tool thất bại không được coi là bằng chứng.
- Tập URL không bị dùng chung giữa các run.

### Kiểm tra riêng H6 với LLM thật

Đã chạy một case bằng cùng cấu hình của baseline; kết quả do runner ghi vào `eval_cp5_h6.json`:

```powershell
. .\setup.ps1
python evals/run_evals.py --case H6 --provider openai --model gpt-4.1-mini --judge-provider openai --judge-model gpt-4.1-mini --max-steps 8 --output eval_cp5_h6.json
```

Trace mới có `validation_missing_source` ở **step 2**, với `observed_urls=["https://stspg.io/7pwv28hvkmz8"]`. Candidate ở step 2 chỉ dẫn các URL do model viết lại, nên bị chặn. Sau yêu cầu sửa, step 3 trả final chứa nguyên URL do tool cung cấp và run `completed`.

| Chỉ số riêng H6 | Trong eval trước | Kiểm tra CP5 |
|---|---:|---:|
| Điểm cuối | 60 | 60 |
| Điểm thô judge | 96 | 95 |
| Model calls của agent | 2 | 3 |
| Token của agent | 2.790 | 6.070 |
| Token của judge | 3.135 | 3.872 |
| Có URL incident đã quan sát trong final | Không | Có |
| Số event `validation_missing_source` | 0 | 1 |

Kết quả xác nhận bước kiểm tra đã can thiệp và model đã bổ sung nguồn. **Điểm vẫn 60**, vì agent chưa đọc incident liên kết và vẫn chỉ có tool calls ở một step. Answer sửa xong vẫn có URL incident liên quan bị thiếu ký tự `7`. Có ít nhất một URL đúng không bảo đảm tất cả URL và mọi kết luận đều đúng.

Đây là kiểm tra **một case**, không phải eval toàn bộ sau cải tiến. Không dùng điểm 60 của file này thay cho điểm tổng CP6 và không gán mọi khác biệt giữa hai câu trả lời cho thay đổi code.

## 4. So sánh hai lần chạy

| Chỉ số | `eval_before.json` | `eval_after.json` |
|---|---|---|
| Điểm tổng | 91,95/100; đủ 22 case | Chờ CP6 |
| Điểm case đã chọn | H6: 60/100 | Chờ CP6 |
| Số model calls | Agent 47; judge 22 | Chờ CP6 |
| Token, chi phí nếu có | Agent 32.046; judge 34.389; tổng 66.435 token; API không trả số tiền | Chờ CP6 |

- Chưa chạy `eval_after.json` đủ 22 case; phần so sánh toàn bộ và kết luận về điểm/chi phí sẽ hoàn thành ở CP6.
- Bước kiểm tra CP5 đã chặn candidate thiếu URL, nhưng kiểm tra riêng H6 vẫn còn lỗi không theo incident liên kết và sai một URL khác. H7 về kết luận khi timeout và H2 về thiếu status chưa được đánh giá lại.

## 5. Giới hạn

- Kiểm tra nguồn chỉ tìm sự xuất hiện nguyên chuỗi của ít nhất một URL đã quan sát; không xác minh mọi URL, mọi claim, phạm vi khách hàng, thời gian hay quan hệ nhân quả.
- Một câu trả lời dùng URL canonical hợp lệ thay vì shortlink do tool trả về vẫn có thể bị yêu cầu sửa; đây là giới hạn của kiểm tra chuỗi theo contract.
- Lượt sửa có thể tăng model calls/token hoặc làm run hết budget. Cần so sánh đầy đủ ở CP6.
- Judge là phép đánh giá xấp xỉ và đang dùng cùng model với agent. CP4 đã quan sát những nhận xét judge không khớp answer/trace, nên phải kiểm tra bằng chứng trực tiếp.
- Snapshot ngày 09/11/2026 không xác nhận trạng thái hiện tại; dữ liệu bị giới hạn lịch sử và một số update bị cắt.
- Một lần chạy mỗi phiên bản hoặc một case đơn lẻ không chứng minh độ ổn định hay cải thiện toàn bộ bộ eval.
