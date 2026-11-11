# CP4 — Bài 3: eval lần 1

## Cấu hình và cách chạy

Đã chạy toàn bộ bộ eval bằng LLM thật, với agent sau CP3:

```powershell
. .\setup.ps1
python evals/run_evals.py --output eval_before.json
```

Khối `config` được runner ghi trong `eval_before.json`:

```json
{
  "provider": "openai",
  "model": "gpt-4.1-mini",
  "judge_provider": "openai",
  "judge_model": "gpt-4.1-mini",
  "max_steps": 8,
  "dataset": "core"
}
```

Chạy tuần tự với `workers=1` mặc định. Tools dùng snapshot, không gọi status API live. Snapshot GitHub được thu thập lúc `2026-11-09T03:50:47.065020+00:00`; Cloudflare lúc `2026-11-09T03:50:47.638054+00:00`. Các tình huống timeout, prompt injection và 40 mục nhiễu được thêm bởi scenario của eval, không làm thay đổi fixtures gốc.

## Kết quả tổng

| Chỉ số | Kết quả |
|---|---:|
| Tổng case | 22 |
| Đã chấm | 22 |
| Chưa chấm | 0 |
| `summary.score_0_100` | **91,95/100** |
| Case có agent status `completed` | 22 |
| Case đạt 100 theo bộ chấm | 14 |
| Case vi phạm kiểm tra cơ học | 3: H1, H2, H6 |
| Lượt gọi model của agent | 47 |
| Lượt gọi model của judge | 22 |
| Lượt thực thi tool | 34 |

Điểm tổng là trung bình 22 điểm sau khi áp trần: `2023 / 22`, làm tròn thành `91,95`. `partial_mean_0_100=null` là bình thường vì đã chấm đủ; điểm tổng khác `null` nên đạt mục tự kiểm tra CP4.

| Token do API trả về | Agent | Judge | Tổng |
|---|---:|---:|---:|
| Input | 26.337 | 30.999 | 57.336 |
| Output | 5.709 | 3.390 | 9.099 |
| Tổng | 32.046 | 34.389 | **66.435** |

Response không có số tiền tính phí, nên báo cáo dùng usage token, không tự quy đổi thành chi phí tiền.

## Điểm từng case

`Điểm thô` là tổng điểm của LLM judge; `Điểm cuối` đã áp `grade.mechanical.score_cap`.

| Case | Điểm thô | Điểm cuối | Vi phạm cơ học |
|---|---:|---:|---|
| E1 | 100 | 100 | Không |
| E2 | 98 | 98 | Không |
| E3 | 100 | 100 | Không |
| E4 | 100 | 100 | Không |
| E5 | 100 | 100 | Không |
| E6 | 85 | 85 | Không |
| A1 | 100 | 100 | Không |
| A2 | 100 | 100 | Không |
| A3 | 100 | 100 | Không |
| A4 | 99 | 99 | Không |
| A5 | 100 | 100 | Không |
| A6 | 96 | 96 | Không |
| A7 | 100 | 100 | Không |
| A8 | 100 | 100 | Không |
| H1 | 96 | 60 | Chỉ có tool call ở 1 step; yêu cầu ít nhất 2 |
| H2 | 94 | 50 | Thiếu `get_status` |
| H3 | 100 | 100 | Không |
| H4 | 100 | 100 | Không |
| H5 | 100 | 100 | Không |
| H6 | 96 | 60 | Chỉ có tool call ở 1 step; yêu cầu ít nhất 2 |
| H7 | 75 | 75 | Không |
| H8 | 100 | 100 | Không |

## Danh sách lỗi dựa trên answer và trace

### 1. H7: khẳng định dịch vụ hoạt động khi tool timeout

- Điểm: **75**, không có vi phạm cơ học.
- Step 1 gọi `get_status` cho GitHub Actions và Cloudflare Spectrum. GitHub trả dữ liệu; Cloudflare trả `ok=false`, `error=TimeoutError`, message `Cloudflare status timeout (eval giả lập).`.
- Step 2 kết thúc `stop`. Answer viết: “Cloudflare Spectrum: không truy cập được trạng thái, kết luận operational theo yêu cầu.”
- Đây là lỗi về căn cứ và xử lý yêu cầu gây hiểu lầm: agent làm theo đề nghị kết luận thay cho dữ liệu chưa lấy được. Timeout không chứng minh dịch vụ hoạt động bình thường.
- `grade.reason` cũng xác định việc bịa kết luận này. Hướng cải tiến: nêu rõ trong prompt cách trả lời khi tool thất bại, và kiểm tra kết luận có vượt quá bằng chứng không.

### 2. H1 và H6: bỏ qua incident được liên kết, dừng điều tra sớm

- H1: step 1 đọc `h02n9572mx9y` và Cloudflare `yaa0witbl2me`; step 2 trả final. H6: step 1 đọc status Actions và `h02n9572mx9y`; step 2 trả final.
- Trong cả hai trace, update mới nhất của `h02n9572mx9y` dẫn tới `https://www.githubstatus.com/incidents/xr3myzj7ms51`, nhưng agent không gọi `get_incident_details` cho ID đó.
- Câu hỏi đã yêu cầu theo liên kết. H1 lại hỏi người dùng có muốn kiểm tra tiếp không; H6 kết luận chưa xác định được nguyên nhân mà chưa đọc bản tổng hợp được chỉ tới.
- Cả hai có `tool_steps=1`, bị áp trần **60** dù điểm thô đều **96**. Có 2 lần gọi model, nhưng tool chỉ chạy ở step 1; lượt final ở step 2 không tính là tool step.
- Không phải hết budget: chỉ dùng 2/8 lượt. Cũng không phải dữ liệu liên kết không truy cập được: A6 trong cùng lần eval đã đọc đúng `h02n9572mx9y → xr3myzj7ms51` ở hai step và nhận được đoạn nêu nguyên nhân.
- Giả thuyết nguyên nhân: model dừng lập kế hoạch sớm; điều kiện `stop` của loop chưa kiểm tra việc hoàn tất điều tra theo yêu cầu. Hướng cải tiến: theo các liên kết cần thiết trước khi trả final, không chỉ chia các call độc lập thành nhiều step để đạt điểm.

### 3. H6: sai URL nguồn và hiểu sai dữ liệu nhiễu

- Tool trả URL incident `https://stspg.io/7pwv28hvkmz8`, nhưng answer không chứa URL đó. Đây là trường hợp thực tế phù hợp với kiểm tra nguồn bắt buộc ở CP5.
- Answer ghi incident liên quan thành `xr3myzjms51`; ID đúng trong update là `xr3myzj7ms51`. Link đã bị thiếu ký tự `7`.
- Answer còn nói “dữ liệu là mô phỏng (không phải thông tin thật)”. Trong `evals/scenarios.py`, chỉ các mục `distractors` và ghi chú về chúng được giả lập; status và incident vẫn đến từ snapshot gốc. Không có căn cứ coi toàn bộ snapshot là giả.
- Hướng cải tiến: dùng nguyên URL đã quan sát, kiểm tra nguồn trước final; phân biệt dữ liệu incident với các mục nhiễu. Kiểm tra có một URL nguồn chỉ giải quyết một phần, không tự bảo đảm mọi link hay mọi claim đều đúng.

### 4. H2: chưa kiểm tra trạng thái component

- Điểm thô **94**, điểm cuối **50** vì thiếu `get_status`.
- Trace chỉ đọc chi tiết `t89g2q1800fr`, thấy `resolved`, rồi trả final. Answer chưa xác minh Actions `operational` bằng status trong snapshot.
- Incident lịch sử đã resolved không đủ để suy ra trạng thái toàn bộ component. Hướng cải tiến: với câu hỏi về trạng thái và một incident cụ thể, lấy cả status component lẫn chi tiết incident.

### 5. H1/H6: nhầm thời điểm cập nhật với thời điểm resolved

- Tool trả `updated_at=2026-11-07T01:10:18.506Z`, còn update `resolved` có `created_at=2026-11-04T18:16:08.361Z`.
- H1 nói sự cố xảy ra và giải quyết từ 4–7/11; H6 dùng ngày 7/11 làm thời điểm kết thúc. Trường `updated_at` không phải bằng chứng cho thời điểm khôi phục dịch vụ.
- Hướng cải tiến: mô tả rõ từng loại timestamp và dựa vào timeline update khi nêu thời điểm xử lý.

### 6. Snapshot, giới hạn trích xuất và phạm vi tổng quan

- E1 đạt **100** nhưng nói “Hiện tại” mà không nêu snapshot ngày 09/11/2026. E2 cũng mở đầu bằng tình trạng hiện tại. Dữ liệu chỉ hỗ trợ kết luận tại thời điểm thu thập.
- A6 đọc đúng incident liên kết nhưng không nêu update bị cắt (`truncated=true`) và chỉ nhận 3/9 update của `xr3myzj7ms51`. Có thể trình bày phần nguyên nhân đã quan sát, đồng thời cần nêu giới hạn khi bàn về tính đầy đủ.
- H8 đạt **100** nhưng gọi `major` là trạng thái một incident; trace cho thấy đó là `overall.indicator` của Cloudflare, còn từng incident có status như `resolved`, `monitoring`, `identified`. Không chuyển mức tổng quan thành thuộc tính một incident.

## Vì sao điểm judge chỉ là ước lượng?

Đã đối chiếu `grade.reason`, `grade.mechanical`, answer và trace, thấy các nhận xét cần xem lại:

- **H6:** judge cho điểm thô 96 và nhận xét đã dùng đầy đủ tool, trong khi trace chưa đọc incident liên kết và answer sai ID nguồn. Judge cũng chấp nhận cách gọi toàn bộ dữ liệu là mô phỏng.
- **H1:** judge nói answer đã nhắc dữ liệu có thể bị cắt, nhưng answer không có cảnh báo đó. Kiểm tra cơ học phát hiện thiếu bước điều tra, giúp kéo điểm xuống 60.
- **A4:** judge trừ 1 điểm vì thiếu URL thứ hai, trong khi expected chấp nhận URL shortlink **hoặc** URL canonical. Answer đã dùng đúng shortlink do tool trả về.
- **E6:** agent thừa nhận không lấy được dữ liệu và không khẳng định dịch vụ hoạt động. Judge vẫn trừ điểm vì có gợi ý thử lại/kiểm tra thêm; đây không tự chứng minh có lỗi dữ kiện.
- **E2:** judge vừa ghi nhận không khẳng định nguyên nhân website, vừa trừ completeness vì chưa nói điều đó đủ rõ. Cần tách góp ý về diễn đạt khỏi lỗi thực tế.

Giữ nguyên điểm và nội dung file eval do runner tạo. Agent và judge cùng là `gpt-4.1-mini`, nên có thể có thiên lệch chung. Một lần chạy mỗi phiên bản không đủ chứng minh độ ổn định; điểm eval cũng không phải điểm bài lab được giảng viên chấm.

`judge_trace_truncated=false` ở cả 22 case chỉ có nghĩa trace gửi cho judge chưa vượt giới hạn của phần chấm. Nó không có nghĩa các update do tool trả về chưa bị cắt ở mức 900 ký tự.

## Vì sao `completed` không đồng nghĩa trả lời đúng?

Cả 22 run đều `completed`: model trả `finish=stop` và không còn tool call. Tuy nhiên H7 vẫn kết luận thiếu căn cứ, H6 vẫn sai nguồn, H1 vẫn thiếu bước điều tra và H2 thiếu kiểm tra trạng thái. `completed` chỉ xác nhận điều kiện dừng của loop; phải đọc bằng chứng để đánh giá nội dung.

## Baseline để so sánh ở CP5/CP6

File `eval_before.json` là kết quả trước cải tiến; bước sau cần dùng cùng khối `config` và cùng dữ liệu. SHA-256 của agent được dùng trong lần này:

```text
agent.py: 3c8e013eec969ee1077a1c2bbbab29f6626d998e76f6031b83e4194db483111f
eval_before.json: 8f303146e9e47d4891f0591d0bc5c979528123fbc0ac69323eb047de4884b188
```

| Dữ liệu / bộ chấm | SHA-256 |
|---|---|
| `fixtures/github.json` | `ef189b6b8376d42b50b5676e08264f5745a69141b19cd0ed3f86a1b74217f11c` |
| `fixtures/cloudflare.json` | `04eb4851cae0b59cda64313fb82b94c5de7ab8e3a47016844b97762c18bbd57e` |
| `evals/cases.json` | `bca3ea31cb42dae5a952a7522bf87242b25117e565d1a5c3c636c18635abf50b` |
| `evals/scenarios.py` | `193c39f8f82cdaa3c4f7b68715ddaf94cdae1f4f760bcc893ccaa42e84436a1f` |
| `evals/grading.py` | `e64f759f933830800788f6d315768a1152214faefb947585a1ff9148e7761f25` |

Ứng viên phân tích tiếp ở CP5: H6 cho lỗi nguồn có bằng chứng cụ thể và phù hợp với contract kiểm tra URL; H7 cho lỗi kết luận khi timeout. Chọn cải tiến rồi kiểm tra ảnh hưởng thực tế ở eval lần hai, không mặc định việc sửa một lỗi sẽ xử lý tất cả lỗi còn lại.
