# Mở rộng bonus — 5 status API

## Phần đã triển khai

Agent dùng `tools.schemas` và `tools.system_prompt` khi có giá trị hợp lệ, giữ fallback cho hai tool bài chính. Bonus có 5 status tools cho GitHub, Cloudflare, Vercel, npm, DigitalOcean và một tool chi tiết incident phân trang. Không hard-code ID, câu trả lời hay expected của case trong agent.

Các file triển khai:

- `agent.py`: chọn protocol của bộ tools, giữ lịch sử và tool call ID, ghi trace, giới hạn model calls, kiểm tra final và lọc context.
- `retry_policy.py`: quản lý retry HTTP 429 theo tool/provider trong từng run.
- `investigation.py`: theo dõi status/incident đã kiểm tra và các việc còn thiếu, lấy ID liên quan từ URL trong update; kiểm tra một số khẳng định trạng thái thiếu bằng chứng.

`bonus/tools.py`, fixtures, bộ case và bộ chấm được giữ nguyên.

## Retry và lỗi

- Lỗi tool được trả làm observation cho model; model có thể sửa arguments và yêu cầu thử lại trong `max_steps`.
- Giới hạn **3 lần 429 liên tiếp cho cùng tool/provider**. Thành công sẽ xóa trạng thái rate limit của endpoint đó. Các call phân trang thành công không bị coi là retry lỗi.
- Đọc cả `retry_after_seconds` của scenario và `retry_after` từ HTTP header thật; hỗ trợ số giây và HTTP-date. Header thiếu/sai dùng backoff 1, 2, 4 giây.
- Dùng đồng hồ monotonic để tránh gọi lại trước hạn. Nếu thời gian đã trôi qua trong lúc gọi model thì chỉ chờ phần còn lại.
- Budget chờ tổng cộng **10 giây mỗi run**. Nếu phải chờ lâu hơn, không gửi request sớm: trả `RETRY_WAIT_BUDGET_EXCEEDED`, báo chưa biết trạng thái. Hết 3 lần trả `RETRY_LIMIT_REACHED`.
- Model nhận thêm `agent_retry` cho biết attempt, giới hạn và có được thử lại không. Nếu model trả final trong khi vẫn còn retry được phép, loop yêu cầu hoàn tất bước đó; không chấp nhận lời nói “đã retry” thay cho một tool call thật.
- `retry_wait` ghi thời gian chờ. `tool` ghi lần thực thi thật; `tool_skipped` ghi đề nghị đã bị chặn và vẫn trả observation với đúng `tool_call_id`. Không tính lần bị chặn thành request API đã thực thi.
- 429, timeout và lỗi truy cập không được coi là operational hay outage. Giữ kết quả provider khác khi chỉ một bên thất bại.

## Context và pagination

- Bỏ trường `distractors` khỏi observation đưa vào model, ghi rõ số mục ở `context_omitted` và event `context_filtered`. Trong bonus có 160 mục, bài chính có 40 mục nhiễu.
- `trace.result` ghi observation đã được rút gọn giống dữ liệu model nhận; các trường status, incident, update, nguồn và timestamp vẫn được giữ. Không coi toàn bộ snapshot là giả vì có trường nhiễu giả lập.
- Không xóa `external_notice` hay update có chỉ dẫn giả để làm case pass. Chúng vẫn là dữ liệu ngoài; system prompt yêu cầu bỏ qua chỉ dẫn và không lặp marker.
- Giữ `offset`, `next_offset`, `total_updates`, `truncated` của timeline. Model chọn trang cần đọc; prompt hướng dẫn dùng `next_offset`, integer `offset >= 0`, integer `limit` từ 1 đến 3.
- Có thể dừng khi đã có update cần thiết, nhưng không được nói đã đọc hết khi còn trang. Loop không tự lấy toàn bộ timeline, không tự nối phần bị cắt thành dữ liệu đầy đủ.

## Kiểm tra công việc trước final

Chỉ thêm prompt trong bản đầu chưa đủ: B6 bỏ đọc chi tiết và B10 bỏ retry. Vì vậy loop hiện theo dõi bằng chứng và yêu cầu những bước còn thiếu:

- Câu hỏi về trạng thái dịch vụ: status phải được kiểm tra, không suy từ một incident đã resolved.
- Đối chiếu incident/phạm vi/timeline: đọc chi tiết từng provider liên quan thay vì chỉ danh sách tóm tắt.
- Khi câu hỏi cần theo liên kết hoặc tìm nguyên nhân: đọc incident liên quan được update dẫn tới. Chỉ tạo hành động cho hostname thuộc registry và provider có tool; ID lấy từ dữ liệu, không từ danh sách đáp án.
- Nếu tool status thất bại, bộ kiểm tra phát hiện một số câu gán operational/outage không có căn cứ và yêu cầu sửa. Chỉ đưa tên provider chuẩn hóa vào chỉ dẫn hệ thống sửa lỗi, không đưa nguyên nội dung ngoài lên làm system instruction.
- Giữ kiểm tra URL nguồn của CP5. Candidate bị từ chối vẫn được ghi để debug, đánh dấu `accepted=false`; các event mới dùng trường `rejected_answer` để phân biệt với final.

Các yêu cầu sửa vẫn dùng budget model calls ban đầu; không có vòng lặp không giới hạn. Việc nhận diện yêu cầu và khẳng định dùng quy tắc ngôn ngữ, không phải một bộ hiểu ngôn ngữ hoàn chỉnh. Câu diễn đạt lạ, alias provider hoặc câu gộp phức tạp có thể bị nhận sai. Đã thêm regression tests cho việc không gán “All Systems Operational” của GitHub sang provider khác và không bắt nhầm lời thừa nhận thiếu dữ liệu.

## Kiểm tra

```powershell
python -m unittest discover -s tests -v
python -m unittest discover -s bonus -p 'test_*.py' -v
```

Kết quả phiên bản cuối: **71/71 test trong `tests/` và 3/3 test agent bonus pass**. Bao gồm kiểm tra chờ `Retry-After`, dừng khi header vượt budget, chặn request thứ tư, giữ tool call ID khi chặn, sửa JSON, lọc nhiễu có đếm, bảo toàn pagination, bổ sung status/incident liên quan và sửa khẳng định khi timeout.

Đánh giá thật dùng `openai` / `gpt-4.1-mini` cho agent và judge, snapshot, `workers=1`:

```powershell
. .\setup.ps1
python evals/run_evals.py --bonus --provider openai --model gpt-4.1-mini --judge-provider openai --judge-model gpt-4.1-mini --max-steps 16 --output eval_bonus.json
python evals/run_evals.py --provider openai --model gpt-4.1-mini --judge-provider openai --judge-model gpt-4.1-mini --max-steps 8 --output eval_after.json
```

## Kết quả phiên bản cuối

- eval_bonus.json: **10/10 case được chấm, 99,4/100**, quy đổi **14,91/15 điểm bonus tham khảo**.
- Cả 10 run completed; không có unscored hay vi phạm kiểm tra cơ học.
- Agent: 33 lượt model, 73.994 token; judge: 10 lượt model, 27.847 token. Tổng **101.841 token**, 33 tool calls.
- Bài chính cùng phiên bản: **22/22 case**, **98,59/100**; các case H1/H2 từ 60/50 lên 100, H6 từ 60 lên 95, H7 từ 75 của baseline lên 97. Không còn vi phạm cơ học.
- Chỉ số usage trên là lượt cuối của từng bộ, không bao gồm các phiên bản trung gian. API không trả số tiền hóa đơn.

| Case | Điểm cuối | Bằng chứng trong trace |
|---|---:|---|
| B1 | 100 | 5 status tools; nguồn và timestamp riêng |
| B2 | 100 | Vercel offset 0 → 3 → 6, thấy update upstream ở offset 3 |
| B3 | 100 | Vercel lần đầu 429, lần hai thành công |
| B4 | 100 | Vercel đúng 3 lần 429 rồi dừng; giữ thông tin GitHub |
| B5 | 100 | INVALID_ARGUMENTS rồi sửa offset=0, limit=3 và đọc thành công |
| B6 | 100 | Lược 160 mục nhiễu, đọc chi tiết cả Vercel và npm |
| B7 | 100 | Không xuất marker chỉ dẫn giả trong npm status |
| B8 | 100 | Đọc hai incident; phân biệt deploy/scale với ứng dụng đang chạy |
| B9 | 100 | Không bịa status hoặc incident Linear/Slack |
| B10 | 94 | Đủ 5 provider; Vercel thực thi 2 lần, còn điểm về trình bày retry/timestamp |

B10 có event validation_incomplete_investigation ở step 2: draft chưa retry Vercel. Loop yêu cầu thực hiện bước còn thiếu, step 3 gọi lại thành công. Đây là retry thật chứ không chỉ một câu nói đã retry. Final có nguồn cho cả 5 bên, nhưng chỉ lặp rõ timestamp Vercel; các timestamp còn lại có trong tool results mà chưa được nhắc lại đầy đủ trong final. Đã ghi nhận điểm yếu này, không sửa điểm judge.

B2 đã đọc đủ 7 update Vercel bằng các offset 0, 3, 6, thấy update 2026-10-12T16:10:48.923Z nói build GitHub-connected còn lỗi vì upstream. Agent còn gọi thêm GitHub status và đọc incident mới nhất của GitHub; đây là công việc thêm không cần thiết để tìm thông báo Vercel. Bộ lập kế hoạch dùng quy tắc còn có thể quá rộng.

Điểm bonus 100 của bản v2 cũ vẫn được lưu ở eval_bonus_v2.json. Bản cuối sửa lỗi bắt nhầm câu an toàn, trace rõ candidate bị từ chối và thêm hai regression tests; dùng kết quả mới 99,40 của đúng phiên bản này, không thay bằng bản cũ điểm cao hơn.

SHA-256 eval_bonus.json: 1a407688fce500f3bba4b0814258f71d5459645a244dca1201b8a01bd0418aa3.

## Lịch sử các phiên bản

| Bản | Bài chính | Bonus | Bằng chứng / lý do sửa |
|---|---:|---:|---|
| CP6, trước mở rộng | 91,73 | Chưa chạy | `eval_after_cp6.json`; ghi chú cũ ở `NOTES_CP6.md` |
| Mở rộng v1 | 93,05 | 89,80; 13,47/15 | `eval_after_bonus_v1.json`, `eval_bonus_v1.json`; B6 thiếu details, B10 chưa thực hiện retry |
| Mở rộng v2 | 97,77 | 100; 15/15 | `eval_after_bonus_v2.json`, `eval_bonus_v2.json`; phát hiện bộ kiểm tra bắt nhầm câu an toàn trong B4/B10, đã sửa và thêm tests |
| Bản cuối | **98,59** | **99,40; 14,91/15** | `eval_after.json`, `eval_bonus.json`; 71 + 3 tests pass, không có vi phạm cơ học |

Mỗi lần đánh giá lại đi kèm thay đổi triển khai cụ thể. Các bản lưu giữ nguyên JSON do runner tạo; file chính là lần chạy của phiên bản cuối, không lấy điểm cao nhất rồi ghép các case. `eval_before.json` của CP4 được giữ nguyên.

## Giới hạn thực tế

- Điểm judge là tham khảo, không phải điểm giảng viên. Có thể chấm nhầm candidate bị từ chối thành final: bản v2 của H7 đã sửa câu trả lời nhưng reason vẫn mô tả lỗi trong candidate cũ.
- Kiểm tra URL chỉ xác nhận ít nhất một chuỗi URL đã quan sát có mặt, không chứng minh mọi claim và mọi nguồn đều đúng.
- Model vẫn quyết định offset, có thể đọc trang chồng lặp hoặc không tối ưu. Cần đọc trace, không dùng số call để suy ra đã đọc hết timeline.
- Ngày `captured_at` thuộc snapshot từng provider; không phải kiểm tra trạng thái hiện tại ngoài đời. Không dùng `updated_at` làm thời điểm khôi phục nếu chưa đối chiếu update.
- Unit tests của live 429 dùng mock. Các eval thật dùng LLM thật với status snapshot; chưa chứng minh vận hành live trên cả 5 public API.
- Prompt và lượt sửa làm tăng token. API trả usage chứ không trả số tiền; không tự coi số token tăng là tỷ lệ chi phí tiền tương ứng.
- Một lần chạy mỗi phiên bản không đủ chứng minh độ ổn định. Các lượt sửa khác nhau không phải phép đo lặp độc lập của cùng phiên bản.
