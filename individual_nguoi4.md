<!--
LƯU Ý TRƯỚC KHI NỘP:
- Đổi tên file này thành đúng chuẩn: individual_5SoCuoiMHV_HoVaTen.md
  (5 số cuối MSSV + Họ tên của Người 4, không dấu cách).
- Điền các trường [ ] còn thiếu (họ tên, MSSV, ngày hoàn thành, kết quả xác
  minh thực tế sau khi chạy batch 50 case).
-->

# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                       |
| --------------- | ----------------------------------------------- |
| Họ và tên       | [Họ và tên]                                     |
| MSSV            | [MSSV]                                          |
| Khóa/Lớp        | K3                                               |
| Vai trò chính   | Người 4 — Coordinator, Integration & Documentation |
| Ngày hoàn thành | [YYYY-MM-DD]                                     |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Coordinator pipeline | `src/coordinator.py` (class `Coordinator`) | `input/EC_XXX.json`, handoff từ Người 1/2/3 | `output/EC_XXX.json`, trace events | Hoàn thành |
| Batch runner | `src/main.py` | 50 file `input/` | Ghi đủ `output/` + `logging/trace.jsonl`, thống kê primary_issue | Hoàn thành |
| LLM reasoning agent | `src/coordinator.py: Coordinator._coordinator_reasoning`, `src/llm_client.py` | Output đã qua Verifier Agent | `summary_vi`, `sanity_check_pass` trong trace (không đổi số liệu output) | Hoàn thành |
| Trace logging | `src/coordinator.py: run_case`, `logging/trace.jsonl` | Kết quả từng agent trong pipeline | 1 dòng JSON/agent/case | Hoàn thành, cần chạy batch thật để sinh file cuối |
| Tài liệu | `architecture.md`, `logging/metadata.json`, báo cáo này | Toàn bộ pipeline đã tích hợp | Tài liệu nộp bài | Hoàn thành |
| Đóng gói | `output.zip` | `output/*.json` | File nộp bài | [Hoàn thành/Chưa hoàn thành — điền sau khi chạy batch] |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Rà soát interface handoff giữa 3 agent | Người 1, Người 2, Người 3 | Xác nhận `Coordinator` gọi đúng `OrderSellerAgent.process()`, `payment_agent.run()`, `delivery_agent.run()`, `policy_agent.evaluate()`, `verifier_agent.verify()` theo đúng contract sẵn có trong `test_person1/2/3.py`, không phải sửa lại code của các bạn. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Ghép pipeline end-to-end 5 agent thành 1 Coordinator class có trace theo từng bước | `src/coordinator.py` | `Coordinator.run_case()` trả `output`, `is_valid`, `errors`, `trace_events` | `python -m src.main` |
| Chạy batch 50 case, ghi output + trace, thống kê primary_issue | `src/main.py` | `output/EC_001.json`..`EC_050.json`, `logging/trace.jsonl` | Xem log console sau khi chạy + đếm file trong `output/` |
| Thêm LLM agent (Groq, llama-3.1-8b-instant) đúng yêu cầu ≤10B tham số mà không ảnh hưởng độ chính xác deterministic | `src/llm_client.py`, `src/coordinator.py` | `logging/metadata.json` khai báo rõ model | Đọc trace, kiểm tra field `coordinator_llm.output` mỗi case |

Một output cụ thể: `logging/trace.jsonl` sau khi chạy `python -m src.main` chứa 6 dòng event cho mỗi case (`case_loaded`, `handoff` x3, `decision`, `verification`, `reasoning`), tổng cộng 300 dòng cho 50 case.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Ba agent (Người 1: Order/Seller, Người 2: Payment/Delivery, Người 3: Policy/Verifier) đã có logic đúng và độc lập, nhưng chưa có một điểm điều phối duy nhất chạy tuần tự cả 5 agent cho 50 case, ghi trace theo từng bước và đóng gói kết quả. `test_person3.py` đã chain được pipeline nhưng chỉ là script test cá nhân, không ghi trace, không có LLM agent, không tách thành module tái sử dụng được.

### Cách triển khai

`Coordinator` (Người 4) import trực tiếp module thật của 3 người (`src.agents.order_seller_agent.OrderSellerAgent`, `agents.payment_agent`, `agents.delivery_agent`, `agents.policy_agent`, `agents.verifier_agent`) — không viết lại logic nghiệp vụ của họ. Với mỗi case, `run_case()` gọi tuần tự 5 agent, ghi 1 trace event JSON sau mỗi bước (agent nào chạy, input rút gọn, output rút gọn), rồi thêm bước LLM reasoning cuối cùng gọi Groq API (`llama-3.1-8b-instant`) để sinh tóm tắt tiếng Việt và tự sanity-check — bước này không có quyền ghi đè số liệu đã được Verifier Agent xác nhận, tránh rủi ro LLM làm sai kết quả chấm điểm trong khi vẫn đáp ứng yêu cầu "mỗi agent dùng model ≤10B tham số".

`src/main.py` dọn `output/` cũ, ghi đè `logging/trace.jsonl` (không append), chạy đủ 50 case, thống kê số case theo từng `primary_issue` và cảnh báo case có `confidence < 0.6` hoặc verifier lỗi.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `input/EC_001.json..EC_050.json`, dữ liệu 5 CSV trong `data/` (qua `DataLoader` của Người 1) |
| Output | `output/EC_XXX.json` đúng schema README mục 6, `logging/trace.jsonl` |
| Module phụ thuộc | `src/agents/order_seller_agent.py`, `agents/payment_agent.py`, `agents/delivery_agent.py`, `agents/policy_agent.py`, `agents/verifier_agent.py` |
| Module sử dụng output | Không có — đây là điểm cuối pipeline trước khi nộp bài |
| Điều kiện lỗi cần xử lý | `claimed_order_id` không tồn tại trong `orders.csv`; Groq API lỗi/timeout (pipeline vẫn chạy tiếp, chỉ thiếu `summary_vi`); Verifier Agent phát hiện lỗi (vẫn ghi output, log cảnh báo để rà soát thủ công) |

### Cách xác minh

```bash
pip install -r requirements.txt
python -m src.main
```

- **Kết quả mong đợi:** in ra thống kê 6 loại `primary_issue`, tổng 50 case, "Verifier PASS toàn bộ 50 case" (hoặc liệt kê case lỗi để sửa), sinh đủ `output/EC_001.json`..`EC_050.json` và `logging/trace.jsonl`.
- **Kết quả thực tế:** [Điền sau khi chạy batch thật — số case mỗi loại, có PASS verifier toàn bộ hay không].
- **Artifact/log:** `output/`, `logging/trace.jsonl`, `logging/metadata.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Người 1/2/3 đã hoàn thành engine quyết định thuần rule-based (deterministic), không gọi LLM nào, trong khi đề bài yêu cầu khai báo và sử dụng model ≤10B tham số trong code.
- **Các phương án đã cân nhắc:**
  1. Viết lại toàn bộ logic quyết định để LLM tự suy luận primary_issue/refund.
  2. Giữ nguyên engine deterministic, thêm một bước LLM riêng biệt sau Verifier Agent chỉ để giải thích/sanity-check.
- **Phương án đã chọn:** Phương án 2.
- **Lý do:** Các rule của `EC_POLICY_V1` là so sánh số liệu/ngày tháng chính xác tuyệt đối; để LLM tự quyết định rủi ro làm sai kết quả chấm điểm (financial_resolution, evidence_ids bị hard-gate nếu sai). Tách LLM thành bước reasoning độc lập sau khi đã verify vừa đáp ứng yêu cầu về model, vừa không đánh đổi độ chính xác đã được test qua `test_person1/2/3.py`.
- **Bằng chứng quyết định phù hợp:** [Điền sau khi chạy batch — ví dụ: "50/50 case verifier PASS, trace có đủ 50 dòng `coordinator_llm.reasoning`"].

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Trong lúc khởi tạo dự án, đã tạo nhầm `src/data_loader.py` và `src/agents/order_seller_agent.py` bản nháp trước khi phát hiện Người 1 đã có module thật cùng vị trí `src/agents/`, dẫn đến xung đột ghi đè tiềm ẩn.
- **Lệnh hoặc bước tái hiện:** Ghi file mới vào `src/agents/order_seller_agent.py` mà chưa đọc file hiện có.
- **Nguyên nhân gốc:** Không kiểm tra lại toàn bộ cây thư mục ngay trước khi ghi, trong khi các thành viên khác đang code song song trên cùng repo.
- **Cách xử lý:** Dừng lại, quét lại toàn bộ thư mục, đọc hết code thật của Người 1/2/3, bỏ hẳn logic nháp trùng lặp, viết `Coordinator` import trực tiếp module thật thay vì tự triển khai lại.
- **Cách xác minh sau khi sửa:** Đọc `src/coordinator.py` xác nhận chỉ import từ `src.agents.order_seller_agent`, `agents.payment_agent`, `agents.delivery_agent`, `agents.policy_agent`, `agents.verifier_agent` — không còn logic nghiệp vụ trùng lặp.
- **Điều học được:** Với repo nhóm chỉnh sửa song song, phải quét lại trạng thái thư mục ngay trước mỗi lần ghi file quan trọng, không giả định trạng thái đã biết từ đầu phiên vẫn còn đúng.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

[Điền theo hiểu biết cá nhân của Người 4 trước khi nộp — ví dụ: dữ liệu đi từ `input/EC_XXX.json` qua `claimed_order_id` để join 5 CSV trong `data/`; mỗi case được Coordinator điều phối tuần tự qua 5 agent, mỗi agent chỉ đọc đúng phạm vi dữ liệu của mình rồi handoff JSON cho agent kế tiếp; Verifier Agent là bước kiểm chất lượng duy nhất trước khi ghi `output/`; LLM reasoning chạy sau cùng nên không ảnh hưởng đến correctness đã được verify; mọi case dùng chung 1 lần load CSV và 1 policy `EC_POLICY_V1` để đảm bảo nhất quán giữa các case.]

## 8. Cam kết của thành viên

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** [Họ và tên]
**Ngày xác nhận:** [YYYY-MM-DD]
