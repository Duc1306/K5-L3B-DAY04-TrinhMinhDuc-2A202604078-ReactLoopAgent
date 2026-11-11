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

### Mở rộng và sửa thêm sau CP6

Sau khi hoàn thành CP6, tiếp tục theo yêu cầu làm bonus và sửa lỗi chưa chắc chắn. Bản ghi CP6 nguyên bản được giữ ở NOTES_CP6.md; kết quả 91,73 được lưu nguyên JSON ở eval_after_cp6.json.

- Agent chọn schemas/system prompt theo bộ tools, hỗ trợ năm provider bonus và timeline phân trang.
- retry_policy.py giới hạn ba lần 429 liên tiếp cho cùng tool/provider, tôn trọng Retry-After, budget chờ 10 giây mỗi run, không gửi request sớm khi header vượt budget.
- investigation.py theo dõi status, incident đã đọc, liên kết cần theo và retry được phép; loop chặn final còn bước cần làm, thay vì chỉ nhắc trong prompt.
- Có thêm kiểm tra một số khẳng định operational/outage khi tool status thất bại. Candidate bị từ chối ghi accepted=false, không được coi là final.
- Lược bỏ trường distractors có ghi số lượng, giữ nguyên dữ liệu status/incident và chỉ dẫn ngoài ở dạng dữ liệu không đáng tin.
- Phiên bản cuối đạt 71/71 test trong tests/ và 3/3 test agent bonus; chi tiết ở BONUS.md. Những số 54 test và lần chạy riêng H6 ở trên là kết quả lịch sử của CP5.

## 4. So sánh hai lần chạy

Bảng dưới đối chiếu baseline CP4 với phiên bản cuối sau mở rộng bonus. Bản sau CP6 cũ và các phiên bản trung gian đều được lưu riêng; không sửa tay hay ghép điểm các file eval.

### Cấu hình và dữ liệu

Khối config của eval_before.json và eval_after.json giống nhau: provider/judge provider openai, model/judge model gpt-4.1-mini, max_steps=8, dataset=core; workers=1. Fixtures, cases, scenarios, grading được kiểm tra SHA-256 và giữ nguyên. Mỗi file có đủ 22 case đã chấm, không có unscored.

Lệnh chạy bản bài chính cuối:

```powershell
. .\setup.ps1
python evals/run_evals.py --provider openai --model gpt-4.1-mini --judge-provider openai --judge-model gpt-4.1-mini --max-steps 8 --output eval_after.json
```

| Chỉ số | eval_before.json | eval_after.json cuối |
|---|---:|---:|
| Điểm tổng | 91,95 | **98,59** |
| H6 được chọn | 60 | **95** |
| Agent completed | 22 | 22 |
| Case vi phạm kiểm tra cơ học | 3: H1, H2, H6 | **0** |
| Model calls của agent | 47 | 59 |
| Model calls của judge | 22 | 22 |
| Tool calls | 34 | 45 |
| Token agent | 32.046 | 90.580 |
| Token judge | 34.389 | 42.554 |
| Tổng token agent + judge | 66.435 | **133.134** |

Điểm công bố tăng **6,64 điểm** so baseline 91,95; tăng **6,86 điểm** so kết quả CP6 cũ 91,73. Tổng token tăng 66.699, khoảng 100,4% so baseline. Prompt dài hơn, đọc thêm bằng chứng và sửa các draft làm tăng chi phí token; đây không phải cải tiến giảm chi phí.

| Usage chi tiết | Trước | Sau |
|---|---:|---:|
| Agent input | 26.337 | 82.287 |
| Agent output | 5.709 | 8.293 |
| Judge input | 30.999 | 38.568 |
| Judge output | 3.390 | 3.986 |

API không trả số tiền tính phí. Chỉ báo token thực tế, không tự quy đổi thành tiền. Các tổng này không cộng chi phí chạy thử H6 hoặc các phiên bản trung gian; mỗi file eval lưu usage của lượt đó.

### Điểm từng case

| Case | Trước | Sau cuối | Chênh lệch |
|---|---:|---:|---:|
| E1 | 100 | 100 | 0 |
| E2 | 98 | 100 | 2 |
| E3 | 100 | 100 | 0 |
| E4 | 100 | 100 | 0 |
| E5 | 100 | 94 | -6 |
| E6 | 85 | 100 | 15 |
| A1 | 100 | 100 | 0 |
| A2 | 100 | 100 | 0 |
| A3 | 100 | 100 | 0 |
| A4 | 99 | 100 | 1 |
| A5 | 100 | 95 | -5 |
| A6 | 96 | 100 | 4 |
| A7 | 100 | 100 | 0 |
| A8 | 100 | 100 | 0 |
| H1 | 60 | 100 | 40 |
| H2 | 50 | 100 | 50 |
| H3 | 100 | 100 | 0 |
| H4 | 100 | 100 | 0 |
| H5 | 100 | 100 | 0 |
| H6 | 60 | 95 | 35 |
| H7 | 75 | 97 | 22 |
| H8 | 100 | 88 | -12 |

### Bằng chứng thay đổi và lỗi còn lại

- **H1, 60 → 100:** đã đọc incident liên kết được update dẫn tới, có tool calls ở ít nhất hai model steps; không còn bị áp trần do dừng điều tra sớm.
- **H2, 50 → 100:** đã lấy status component ngoài chi tiết incident resolved; không còn suy trạng thái dịch vụ chỉ từ incident lịch sử.
- **H6, 60 → 95:** trace đọc status Actions, h02n9572mx9y rồi xr3myzj7ms51; final có cả nguồn incident gốc và incident gộp, trình bày phần nguyên nhân từ update đã quan sát. 40 mục nhiễu được lược bỏ có ghi nhận. Đây là thay đổi về chuỗi điều tra, không chỉ thêm URL như CP5.
- **H7, 75 → 97:** loop từ chối hai candidate khẳng định trạng thái không có bằng chứng. Final nói Cloudflare chưa xác nhận được do timeout, giữ nguồn GitHub. Tuy nhiên final **nói sai đã thử tối đa 3 lần** trong khi trace chỉ có **một lần** gọi status Cloudflare, và vẫn nhắc nhãn nội bộ next_actions. Kiểm tra này chưa bảo đảm mọi câu về quá trình thực thi đều chính xác.
- **H8, 100 → 88:** vẫn thừa nhận không có lịch sử đầy đủ 2020–2026, nhưng nói đã kiểm tra toàn bộ 50 incident trong khi get_status chỉ hiển thị 5. Cần phân biệt tập tìm kiếm 50 với số bản ghi thực sự được trả về.
- **A5, 100 → 95:** thừa nhận giới hạn năm 2025 nhưng nói đã tải 6 chi tiết; trace thực tế chỉ đọc 5 incident và answer liệt kê 5. Số lượng trong văn bản và trace chưa khớp.
- **E5, 100 → 94:** final thực tế đã nhắc giới hạn 50 incident, nhưng judge vẫn ghi thiếu nhấn mạnh giới hạn đó. H6 còn chưa nói rõ cờ truncated=true; mô tả nguyên nhân chỉ là phần update được trích.
- Các điểm tăng/giảm riêng lẻ vẫn có dao động từ model và judge. Không gán mọi thay đổi cho code nếu không có event hay tool call làm bằng chứng.

Bản cuối có 2 event validation_incomplete_investigation và 2 event validation_unsupported_status. Các yêu cầu sửa đều nằm trong max_steps. Không có run max_steps/error trong lần này; điều đó không chứng minh mọi answer đều đúng.

### Bonus và các bản lưu

Bonus cuối chấm đủ **10/10 case**, **99,4/100**, quy đổi **14,91/15 điểm tham khảo**; không có vi phạm cơ học. B1–B9 đạt 100, B10 đạt 94. Dùng cùng provider/model nhưng dataset=bonus, max_steps=16 theo đề; không đem điểm của bộ 10 case thay cho bộ chính 22 case.

| File | Vai trò | Điểm |
|---|---|---:|
| eval_before.json | Baseline CP4 | 91,95 |
| eval_after_cp6.json | Bản CP6 được lưu nguyên | 91,73 |
| eval_after_bonus_v1.json | Nối bonus, thêm policy/prompt, chưa kiểm tra đầy đủ bước điều tra | 93,05 |
| eval_bonus_v1.json | B6 thiếu details, B10 chưa retry thật | 89,80; 13,47/15 |
| eval_after_bonus_v2.json | Thêm kiểm tra công việc trước final | 97,77 |
| eval_bonus_v2.json | Bản trước khi sửa bắt nhầm câu an toàn | 100; 15/15 |
| eval_after.json | Phiên bản triển khai cuối | **98,59** |
| eval_bonus.json | Phiên bản triển khai cuối | **99,4; 14,91/15** |

File chính dùng lượt của phiên bản cuối, dù điểm bonus thấp hơn bản v2 đã lưu. Mỗi lượt đánh giá lại gắn với thay đổi code có lý do và test; không chọn điểm cao nhất hoặc ghép case. Đọc BONUS.md để xem retry, pagination, context, nguồn và bằng chứng từng case.

```text
agent.py cuối: f8a768150e13e7ca10831662837ce29a528cec20546aa184e9d7704f85e37d5b
retry_policy.py: 399089d035d76a1ebfcf970b293ebfa3c820288eff71e7b01ab5e81b4b58d6ec
investigation.py: 7e48a640abc25ada37e085b3f0ece78286ed8f977b237021d6ec025d4a079541
eval_before.json: 8f303146e9e47d4891f0591d0bc5c979528123fbc0ac69323eb047de4884b188
eval_after.json: 920f7e8319759fef8770984d1a2782c41e3a317f83838389ff833b4900fbd22f
eval_bonus.json: 1a407688fce500f3bba4b0814258f71d5459645a244dca1201b8a01bd0418aa3
```

## 5. Giới hạn

- Một lượt eval mỗi phiên bản không chứng minh độ ổn định. Các phiên bản trung gian khác code nên không phải phép đo lặp độc lập của cùng một agent; chưa có khoảng tin cậy hay phân bố lỗi.
- Judge cùng model với agent có thể có thiên lệch và nhầm candidate bị từ chối với final. Ở bản v2, H7 final đúng về trạng thái chưa xác nhận nhưng reason vẫn mô tả lỗi cũ. Bản cuối giữ rejected_answer và accepted=false rõ hơn; không chỉnh điểm bằng tay.
- Cả 22 run completed chỉ xác nhận điều kiện dừng. H7, A5 và H8 vẫn có phát biểu về số lần thử/số dữ liệu không khớp trace dù điểm cao. Điểm eval không thay thế chấm bài lab của giảng viên.
- Kiểm tra URL chỉ xác nhận ít nhất một URL đã quan sát xuất hiện; không chứng minh mọi URL, mọi kết luận và mọi phạm vi ảnh hưởng đều đúng.
- Kiểm tra yêu cầu và câu khẳng định dùng quy tắc ngôn ngữ, có thể bỏ sót hoặc bắt nhầm. Không phải một bộ kiểm chứng sự thật tổng quát. Đã sửa trường hợp gán “All Systems Operational” của GitHub sang provider khác, nhưng không bảo đảm mọi câu ghép/alias đều được hiểu đúng.
- Kế hoạch có thể đọc thêm ngoài nhu cầu: B2 bonus đã tìm được update Vercel nhưng còn gọi GitHub status và đọc incident mới nhất của GitHub. Đây là chi phí thêm, không tự chứng minh quan hệ nhân quả với sự cố lịch sử Vercel.
- Snapshot GitHub/Cloudflare ngày 09/11/2026, ba provider bổ sung ngày 10/11/2026 không xác nhận tình trạng live hôm nay. Tập tìm kiếm và số mục trả về khác nhau; update có thể bị cắt và timeline còn trang chưa xem.
- Retry có giới hạn thời gian và số lần. Live 429/Retry-After được kiểm thử bằng mock; các eval dùng LLM thật với status snapshot, chưa chứng minh vận hành live trên tất cả public API.
- Prompt và bước kiểm tra làm tăng token, đôi khi tăng cả lượt model và tool. Dữ liệu báo usage không phải số tiền hóa đơn; cần cân nhắc độ đúng và chi phí cùng nhau.
