# B?n l?u ghi ch? CP6

B?n ghi tr??c khi m? r?ng bonus v? s?a th?m v?ng ?i?u tra. C?c nh?c ??n `eval_after.json` b?n d??i t??ng ?ng v?i file ???c l?u nguy?n v?n th?nh `eval_after_cp6.json` (91,73/100).

---

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

Đã chạy toàn bộ eval lần hai bằng agent sau CP5, ghi kết quả vào `eval_after.json`:

```powershell
. .\setup.ps1
python evals/run_evals.py --provider openai --model gpt-4.1-mini --judge-provider openai --judge-model gpt-4.1-mini --max-steps 8 --output eval_after.json
```

Hai file có khối `config` giống nhau: provider/judge provider `openai`, model/judge model `gpt-4.1-mini`, `max_steps=8`, `dataset=core`. Cả hai chạy tuần tự với `workers=1`, cùng snapshot và cùng 22 case. Đã kiểm tra SHA-256: fixtures, cases, scenarios, grading và `eval_before.json` giữ nguyên; agent dùng cho CP6 đúng phiên bản đã kiểm tra ở CP5.

| Chỉ số | `eval_before.json` | `eval_after.json` |
|---|---|---|
| Điểm tổng | **91,95/100** | **91,73/100** |
| Số case đã chấm | 22/22; không có unscored | 22/22; không có unscored |
| Agent status `completed` | 22 | 22 |
| Điểm case đã chọn | H6: 60; điểm thô 96 | H6: 60; điểm thô 93 |
| Số model calls | Agent 47; judge 22; tổng 69 | Agent 48; judge 22; tổng 70 |
| Tool calls | 34 | 34 |
| Case vi phạm kiểm tra cơ học | H1, H2, H6 | H1, H2, H6 |
| Case đạt 100 theo bộ chấm | 14 | 14 |
| Event `validation_missing_source` | 0 | 1, ở H6 step 2 |
| Case đọc incident thành công nhưng final thiếu mọi URL incident đã quan sát | H6 | Không có |

Điểm tổng được báo giảm **0,22 điểm** khi so hai giá trị đã làm tròn. Tổng điểm 22 case giảm từ 2.023 xuống 2.018. Hai case tăng điểm, bốn case giảm điểm và 16 case giữ nguyên.

### Token và chi phí

| Usage do API trả về | Trước | Sau | Thay đổi |
|---|---:|---:|---:|
| Agent input | 26.337 | 28.738 | +2.401 |
| Agent output | 5.709 | 6.012 | +303 |
| Agent tổng | 32.046 | 34.750 | +2.704; khoảng +8,44% |
| Judge input | 30.999 | 31.276 | +277 |
| Judge output | 3.390 | 3.328 | -62 |
| Judge tổng | 34.389 | 34.604 | +215 |
| **Tổng agent + judge** | **66.435** | **69.354** | **+2.919; khoảng +4,39%** |

API không trả số tiền tính phí trong response; không tự quy đổi token thành chi phí tiền. Các số trên chỉ tính hai lần eval đầy đủ, không cộng lần kiểm tra riêng H6 ở CP5. Token khác nhau còn do độ dài câu trả lời và nhận xét judge thay đổi; không coi toàn bộ chênh lệch token là chi phí riêng của bước kiểm tra nguồn.

### Điểm từng case

| Case | Trước | Sau | Chênh lệch |
|---|---:|---:|---:|
| E1 | 100 | 100 | 0 |
| E2 | 98 | 98 | 0 |
| E3 | 100 | 100 | 0 |
| E4 | 100 | 100 | 0 |
| E5 | 100 | 100 | 0 |
| E6 | 85 | 100 | +15 |
| A1 | 100 | 100 | 0 |
| A2 | 100 | 100 | 0 |
| A3 | 100 | 100 | 0 |
| A4 | 99 | 100 | +1 |
| A5 | 100 | 98 | -2 |
| A6 | 96 | 94 | -2 |
| A7 | 100 | 98 | -2 |
| A8 | 100 | 100 | 0 |
| H1 | 60 | 60 | 0 |
| H2 | 50 | 50 | 0 |
| H3 | 100 | 100 | 0 |
| H4 | 100 | 100 | 0 |
| H5 | 100 | 100 | 0 |
| H6 | 60 | 60 | 0 |
| H7 | 75 | 60 | -15 |
| H8 | 100 | 100 | 0 |

### Lỗi nguồn được xử lý trong H6

Trace của H6 trong `eval_after.json` có chuỗi:

1. Step 1: `get_status(github, actions)` và `get_incident_details(github, h02n9572mx9y)`; tool chi tiết trả `https://stspg.io/7pwv28hvkmz8`.
2. Step 2: model đề xuất final nhưng chỉ dẫn nguồn trang tổng quan và URL incident liên quan. Loop ghi `validation_missing_source`, với `observed_urls=["https://stspg.io/7pwv28hvkmz8"]`, và yêu cầu sửa.
3. Step 3: model trả final chứa nguyên URL incident đã quan sát; run `completed`.

Trích từ final mới:

```text
- Trang nguồn chính cho incident này tại URL: https://stspg.io/7pwv28hvkmz8
```

Đây là bằng chứng trực tiếp bước kiểm tra đã chặn candidate thiếu URL và khiến model bổ sung nguồn. H6 dùng 3 model calls thay vì 2; đây cũng là case duy nhất có thêm model call trong lần eval đầy đủ. Token riêng H6 thay đổi: agent 2.790 → 5.676, judge 3.135 → 3.612; tổng 5.925 → 9.288. Các con số này thuộc CP6, khác với lần kiểm tra đơn lẻ ở mục 3.

### Lỗi còn lại và điểm yếu quan sát thêm

- **H1/H6 vẫn thiếu bước điều tra:** trace chỉ có tool calls ở step 1, không đọc `xr3myzj7ms51` được incident đầu dẫn tới. Cả hai vẫn bị áp trần 60. Việc thêm một lượt sửa final không tạo thêm tool step, nên không đáp ứng yêu cầu điều tra nhiều bước.
- **H6 vẫn kết luận quá bằng chứng:** final nói bản tổng hợp liên kết không nêu nguyên nhân chính thức dù chưa đọc bản tổng hợp đó. Trên cùng snapshot, A6 đọc được `xr3myzj7ms51` và nhận đoạn nêu nguyên nhân. URL đã đúng chưa làm kết luận này trở nên đúng. Final CP6 không còn hiển thị URL sai ID như baseline, nhưng không thể suy ra lỗi viết sai mọi URL đã được giải quyết.
- **H2 vẫn thiếu `get_status`:** chỉ đọc incident lịch sử đã resolved rồi trả lời, chưa kiểm tra trạng thái component trong snapshot; điểm giữ ở 50.
- **H7 vẫn bịa trạng thái khi timeout, điểm giảm 75 → 60:** Cloudflare trả `ok=false`, `error=TimeoutError`, nhưng final viết “cả hai dịch vụ GitHub Actions và Cloudflare Spectrum đều đang operational tại thời điểm kiểm tra.” Lần này nguồn GitHub chỉ được nêu tên, không có URL cụ thể. Không có incident được đọc thành công nên bước kiểm tra URL incident không áp dụng cho case này.
- **H1 vẫn nhầm thời điểm:** answer gọi ngày 07/11 là lúc kết thúc, dựa vào `updated_at`, trong khi update `resolved` được tạo ngày 04/11. Kiểm tra URL không xác minh timeline.
- **A6 vẫn thiếu cảnh báo giới hạn trích xuất:** đọc được incident liên kết có update `truncated=true`, nhưng answer không nêu rõ phần bị cắt; judge góp ý tách thông tin được và chưa được xác nhận. Điểm giảm 96 → 94.
- **E6/A4 tăng điểm, A5/A7 giảm nhẹ, không có event sửa nguồn:** E6 vẫn thừa nhận timeout, A4 vẫn bỏ qua injection và dùng đúng shortlink. Judge của A5 muốn danh sách chi tiết hơn, A7 muốn bước kiểm tra log cụ thể hơn. Không có bằng chứng gán những thay đổi điểm này cho bước kiểm tra nguồn ở CP5.

Kết quả thực tế: điều kiện chấp nhận final về URL được cải thiện và can thiệp đúng một case, nhưng điểm tổng không tăng; các lỗi điều tra và xử lý thiếu dữ liệu vẫn còn. Không sửa điểm hay nội dung hai file eval do runner tạo, và không chạy lại để chọn kết quả có điểm cao hơn.

### Dấu vết phiên bản

```text
agent.py dùng ở CP6: 6081cbe037ccb747a64e40e313105b57c37ed3f4339e166f6143bb415631ed3c
eval_before.json: 8f303146e9e47d4891f0591d0bc5c979528123fbc0ac69323eb047de4884b188
eval_after.json: 046052941f7ea51e926f4a039e9f8f3ff6c22c19725c29afd83bf12113693caf
```

## 5. Giới hạn

- Kiểm tra nguồn chỉ tìm sự xuất hiện nguyên chuỗi của ít nhất một URL đã quan sát; không xác minh mọi URL, mọi claim, phạm vi khách hàng, thời gian hay quan hệ nhân quả.
- Một câu trả lời dùng URL canonical hợp lệ thay vì shortlink do tool trả về vẫn có thể bị yêu cầu sửa; đây là giới hạn của kiểm tra chuỗi theo contract.
- Lượt sửa có thể tăng model calls/token hoặc làm run hết budget. Trong lần này agent tăng một model call, tổng token agent + judge tăng 4,39%; cả 22 run vẫn `completed`, không có run `max_steps` hay `error`. Kết quả này không chứng minh budget sẽ luôn đủ ở các lần khác.
- Judge là phép đánh giá xấp xỉ và đang dùng cùng model với agent, có thể có thiên lệch chung. CP6 vẫn thấy nhận xét không khớp bằng chứng: judge H6 nói nguồn cuối là trang tổng quan dù final đã chứa shortlink; judge H1 trừ factuality một phần vì cách diễn đạt “đã giải quyết” trong khi answer có ghi `Resolved`. Điểm và reason phải được đối chiếu với answer/trace.
- Kiểm tra cơ học bắt được việc thiếu tool hoặc tool step, nhưng không xác minh hết nội dung. H7 không có vi phạm cơ học dù trả lời sai về Cloudflare. Tất cả run `completed` cũng chỉ xác nhận loop dừng bình thường.
- `judge_trace_truncated=false` ở cả hai file không đồng nghĩa dữ liệu tool đầy đủ: tool vẫn giới hạn 50 incident, số update và 900 ký tự mỗi update. Snapshot ngày 09/11/2026 không xác nhận trạng thái dịch vụ hiện tại.
- Chỉ có một lần eval đầy đủ trước và một lần sau với cấu hình giống nhau; model và judge vẫn có thể tạo kết quả khác nhau. Có thêm một lần kiểm tra riêng H6 ở CP5 nhưng không đủ đánh giá độ ổn định cho 22 case. Chưa có phân bố điểm, khoảng tin cậy hay kiểm tra lặp lại để tách ảnh hưởng của code khỏi dao động giữa các lần gọi.
- Vì vậy chỉ kết luận được điều kiện kiểm tra nguồn đã hoạt động trên trace quan sát. Không chứng minh cải thiện điểm tổng hoặc độ tin cậy chung; cần các lần đánh giá có kiểm soát tiếp theo nếu muốn đưa ra kết luận rộng hơn. Điểm eval không thay thế điểm bài lab của giảng viên.
