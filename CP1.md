# CP1 — Setup và khám phá tools

## Kết quả setup

- Repo: `Duc1306/K5-L3B-DAY04-TrinhMinhDuc-2A202604078-ReactLoopAgent`, đúng mẫu tên lớp L3B, đã clone về máy và đang public.
- `origin` trỏ đến repo cá nhân; `upstream` trỏ đến repo đề `VinUni-AI20k/K5-L3-Day4-ReactLoopAgent`.
- Python: **3.12.10**, đạt yêu cầu Python 3.10+; bài dùng standard library nên không cần cài package.
- Cấu hình có trong `.env`: `PROVIDER=openai`, `MODEL=gpt-4.1-mini`, đã có `OPENAI_API_KEY`.
- Đã gọi API thật một lần với schemas của bài: `finish=tool_calls`, model gọi `get_status` với `provider=github`, `component=Actions`. Usage: 158 input + 18 output = **176 token**. Key và khả năng tool calling đã được kiểm tra.
- `.env` được Git bỏ qua và không nằm trong danh sách file được theo dõi; `.env.example` được theo dõi.
- Đã chạy `git push origin main` thành công, kết quả `Everything up-to-date` khi kiểm tra kết nối/quyền push trước khi ghi tài liệu CP1.

## Chạy lại trong PowerShell

Python không tự đọc `.env`. Mỗi terminal mới, đứng tại thư mục repo và nạp biến vào terminal đó:

```powershell
. .\setup.ps1
python --version
python -c "import json; from status_tools import StatusTools; print(json.dumps(StatusTools().get_status('github', 'Actions'), ensure_ascii=False, indent=2))"
python -c "import json; from status_tools import StatusTools; print(json.dumps(StatusTools().get_incident_details('cloudflare', 'wp49bp8bqo6c'), ensure_ascii=False, indent=2))"
```

`setup.ps1` chỉ đọc các biến cấu hình được cho phép từ `.env` vào môi trường của tiến trình PowerShell; không thực thi nội dung file. Hai tool có thể chạy riêng mà không cần LLM key.

## Câu 1: Hai tool trả về gì?

### `get_status(provider, component='')`

Trả về dict có thể in thành JSON, gồm nhà cung cấp (`provider`), thời điểm thu thập (`captured_at`), trạng thái tổng quan (`overall`), các component khớp (`components`, tối đa 5), các incident khớp (`incidents`, tối đa 5), số incident khớp trong tập 50 incident gần nhất (`matching_incidents_in_last_50`), lưu ý giới hạn (`note`) và nguồn (`source`). Mỗi incident có ID, tên, trạng thái và thời điểm cập nhật.

Kết quả chạy `get_status('github', 'Actions')` trên snapshot:

- Snapshot được thu thập lúc `2026-11-09T03:50:47.065020+00:00`.
- `overall`: `indicator=none`, `description=All Systems Operational`.
- Component `Actions`: `operational`.
- Có **23 incident khớp** trong tập tìm kiếm; JSON chỉ hiển thị **5** incident, cả 5 đều `resolved`.

Vì vậy, tại thời điểm snapshot, Actions hoạt động bình thường dù có các incident lịch sử đã xử lý. Không lấy việc xuất hiện incident lịch sử làm bằng chứng rằng dịch vụ đang lỗi.

### `get_incident_details(provider, incident_id)`

Trả về chi tiết một incident: `ok`, nhà cung cấp, thời điểm snapshot, ID, tên, trạng thái, thời điểm tạo/cập nhật, các component bị ảnh hưởng, các update (`updates`), tổng số update (`updates_total`) và URL incident (`url`). Nếu không thấy ID trong tập dữ liệu, trả `ok=false`, `error=INCIDENT_NOT_FOUND`.

Tool chỉ giữ **hai update mới nhất và update đầu tiên** nếu có hơn hai update; mỗi nội dung update tối đa **900 ký tự**. `truncated` cho biết nội dung update bị cắt; so sánh `updates_total` với số update trả về để biết timeline có bị lược bớt không.

Kết quả chạy `get_incident_details('cloudflare', 'wp49bp8bqo6c')`:

- `ok=true`, tên incident: **Fedramp Customers have Delayed Purges**.
- Trạng thái trong snapshot: `identified`; component: `CDN Cache Purge`.
- Tạo lúc `2026-11-06T17:47:15.545Z`, cập nhật lúc `2026-11-06T17:59:13.680Z`.
- Có **2 update**, cả hai được trả đầy đủ (`truncated=false`).
- Nội dung cho biết lỗi purge pipeline ảnh hưởng **khách hàng FedRAMP**, có thể tiếp tục phục vụ nội dung cũ đến khi hết hạn; khách hàng ngoài FedRAMP không bị ảnh hưởng.
- URL do tool trả về: `https://www.cloudflarestatus.com/incidents/wp49bp8bqo6c`.

## Câu 2: Vì sao tìm không thấy không chứng minh incident không tồn tại?

Vì công cụ tìm kiếm có giới hạn về dữ liệu và cách khớp:

1. **Phạm vi lịch sử:** chỉ tra tập 50 incident gần nhất, nên incident cũ hơn có thể nằm ngoài tập đó.
2. **Khớp chuỗi:** `component` được chuyển về chữ thường và tìm như một chuỗi con trong tên, component và nội dung update; không hiểu từ đồng nghĩa hay dịch ngôn ngữ. `cache purge` có thể khớp trong khi `xóa bộ nhớ đệm` không khớp cùng dữ liệu.
3. **Thời điểm dữ liệu:** chế độ mặc định đọc snapshot ngày **09/11/2026**, nên không phản ánh những sự cố mới xuất hiện sau đó. Đây không phải kết luận về tình trạng hiện tại.
4. **Giới hạn hiển thị:** có thể có nhiều kết quả khớp nhưng `incidents` chỉ trả tối đa 5. Không thấy một incident trong danh sách này chưa đủ để kết luận nó không có trong dữ liệu.

Cách trả lời phù hợp: **“Không tìm thấy incident khớp từ khóa trong phạm vi dữ liệu đã kiểm tra.”** Khi cần điều tra thêm, thử tên component hoặc từ khóa tiếng Anh khác, bỏ bộ lọc, đọc chi tiết ID liên quan, hoặc dùng `live` và kiểm tra nguồn chính thức để mở rộng lịch sử. Timeout/lỗi truy cập cũng chỉ có nghĩa là chưa kiểm tra được, không có nghĩa dịch vụ đang hoạt động bình thường.
