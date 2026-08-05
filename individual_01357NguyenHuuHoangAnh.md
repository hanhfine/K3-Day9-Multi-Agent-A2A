# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                                             |
| ------------------ | ----------------------------------------------------- |
| Họ và tên       | Nguyễn Hữu Hoàng Anh                               |
| MSSV               | 2A202601357                                           |
| Khóa/Lớp         | K3                                                    |
| Vai trò chính    | Người 4 — Coordinator, Integration & Documentation |
| Ngày hoàn thành | 2026-08-05                                            |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable   | File/hàm phụ trách                                                             | Input nhận vào                                 | Output bàn giao                                                                  | Trạng thái |
| -------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------ | --------------------------------------------------------------------------------- | ------------ |
| Coordinator pipeline | `src/coordinator.py` (class `Coordinator`)                                    | `input/EC_XXX.json`, handoff từ Người 1/2/3 | `output/EC_XXX.json`, trace events                                              | Hoàn thành |
| Batch runner         | `src/main.py`                                                                   | 50 file`input/`                                | Ghi đủ`output/` + `logging/trace.jsonl`, thống kê primary_issue           | Hoàn thành |
| LLM reasoning agent  | `src/coordinator.py: Coordinator._coordinator_reasoning`, `src/llm_client.py` | Output đã qua Verifier Agent                   | `summary_vi`, `sanity_check_pass` trong trace (không đổi số liệu output) | Hoàn thành |
| Trace logging        | `src/coordinator.py: run_case`, `logging/trace.jsonl`                         | Kết quả từng agent trong pipeline             | 1 dòng JSON/agent/case                                                           | Hoàn thành |
| Tài liệu           | `architecture.md`, `logging/metadata.json`, báo cáo này                    | Toàn bộ pipeline đã tích hợp               | Tài liệu nộp bài                                                              | Hoàn thành |
| Đóng gói          | `output.zip`                                                                    | `output/*.json`                                | File nộp bài                                                                    | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                              | Thành viên/module được hỗ trợ | Kết quả                                                                                                                                                                                                                                                                                  |
| ----------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Rà soát interface handoff giữa 3 agent | Người 1, Người 2, Người 3      | Xác nhận`Coordinator` gọi đúng `OrderSellerAgent.process()`, `payment_agent.run()`, `delivery_agent.run()`, `policy_agent.evaluate()`, `verifier_agent.verify()` theo đúng contract sẵn có trong `test_person1/2/3.py`, không phải sửa lại code của các bạn. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện                                                                                                         | File/hàm/artifact liên quan                 | Kết quả bàn giao                                                                    | Cách xác minh                                                  |
| ----------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- | -------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Ghép pipeline end-to-end 5 agent thành 1 Coordinator class có trace theo từng bước                                            | `src/coordinator.py`                        | `Coordinator.run_case()` trả `output`, `is_valid`, `errors`, `trace_events` | `python -m src.main`                                           |
| Chạy batch 50 case, ghi output + trace, thống kê primary_issue                                                                   | `src/main.py`                               | `output/EC_001.json`..`EC_050.json`, `logging/trace.jsonl`                       | Xem log console sau khi chạy + đếm file trong`output/`      |
| Thêm LLM agent (Groq, llama-3.1-8b-instant) đúng yêu cầu ≤10B tham số mà không ảnh hưởng độ chính xác deterministic | `src/llm_client.py`, `src/coordinator.py` | `logging/metadata.json` khai báo rõ model                                          | Đọc trace, kiểm tra field`coordinator_llm.output` mỗi case |

Một output cụ thể: `logging/trace.jsonl` sau khi chạy `python -m src.main` chứa 7 dòng event cho mỗi case (`case_loaded`, `handoff` x3, `decision`, `verification`, `reasoning`), tổng cộng 350 dòng cho 50 case (thực đo từ lần chạy thật).

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Ba agent (Người 1: Order/Seller, Người 2: Payment/Delivery, Người 3: Policy/Verifier) đã có logic đúng và độc lập, nhưng chưa có một điểm điều phối duy nhất chạy tuần tự cả 5 agent cho 50 case, ghi trace theo từng bước và đóng gói kết quả. `test_person3.py` đã chain được pipeline nhưng chỉ là script test cá nhân, không ghi trace, không có LLM agent, không tách thành module tái sử dụng được.

### Cách triển khai

`Coordinator` (Người 4) import trực tiếp module thật của 3 người (`src.agents.order_seller_agent.OrderSellerAgent`, `agents.payment_agent`, `agents.delivery_agent`, `agents.policy_agent`, `agents.verifier_agent`) — không viết lại logic nghiệp vụ của họ. Với mỗi case, `run_case()` gọi tuần tự 5 agent, ghi 1 trace event JSON sau mỗi bước (agent nào chạy, input rút gọn, output rút gọn), rồi thêm bước LLM reasoning cuối cùng gọi Groq API (`llama-3.1-8b-instant`) để sinh tóm tắt tiếng Việt và tự sanity-check — bước này không có quyền ghi đè số liệu đã được Verifier Agent xác nhận, tránh rủi ro LLM làm sai kết quả chấm điểm trong khi vẫn đáp ứng yêu cầu "mỗi agent dùng model ≤10B tham số".

`src/main.py` dọn `output/` cũ, ghi đè `logging/trace.jsonl` (không append), chạy đủ 50 case, thống kê số case theo từng `primary_issue` và cảnh báo case có `confidence < 0.6` hoặc verifier lỗi.

### Input, output và contract

| Thành phần                   | Mô tả                                                                                                                                                                                                                                |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Input                          | `input/EC_001.json..EC_050.json`, dữ liệu 5 CSV trong `data/` (qua `DataLoader` của Người 1)                                                                                                                                |
| Output                         | `output/EC_XXX.json` đúng schema README mục 6, `logging/trace.jsonl`                                                                                                                                                            |
| Module phụ thuộc             | `src/agents/order_seller_agent.py`, `agents/payment_agent.py`, `agents/delivery_agent.py`, `agents/policy_agent.py`, `agents/verifier_agent.py`                                                                              |
| Module sử dụng output        | Không có — đây là điểm cuối pipeline trước khi nộp bài                                                                                                                                                                    |
| Điều kiện lỗi cần xử lý | `claimed_order_id` không tồn tại trong `orders.csv`; Groq API lỗi/timeout (pipeline vẫn chạy tiếp, chỉ thiếu `summary_vi`); Verifier Agent phát hiện lỗi (vẫn ghi output, log cảnh báo để rà soát thủ công) |

### Cách xác minh

```bash
pip install -r requirements.txt
python -m src.main
```

- **Kết quả mong đợi:** in ra thống kê 6 loại `primary_issue`, tổng 50 case, "Verifier PASS toàn bộ 50 case" (hoặc liệt kê case lỗi để sửa), sinh đủ `output/EC_001.json`..`EC_050.json` và `logging/trace.jsonl`.
- **Kết quả thực tế:** Chạy `python -m src.main` thành công 50/50 case, Verifier PASS toàn bộ 50 case (0 lỗi), 0 case confidence < 0.6, đủ cả 6 loại `primary_issue` (late_delivery_seller: 8, unsupported_late_claim: 9, canceled_order_paid: 8, valid_split_payment: 9, unavailable_order_paid: 8, late_delivery_logistics: 8), sinh đủ `output/EC_001.json`..`EC_050.json` và `logging/trace.jsonl` (350 dòng).
- **Artifact/log:** `output/`, `logging/trace.jsonl`, `logging/metadata.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Người 1/2/3 đã hoàn thành engine quyết định thuần rule-based (deterministic), không gọi LLM nào, trong khi đề bài yêu cầu khai báo và sử dụng model ≤10B tham số trong code.
- **Các phương án đã cân nhắc:**
  1. Viết lại toàn bộ logic quyết định để LLM tự suy luận primary_issue/refund.
  2. Giữ nguyên engine deterministic, thêm một bước LLM riêng biệt sau Verifier Agent chỉ để giải thích/sanity-check.
- **Phương án đã chọn:** Phương án 2.
- **Lý do:** Các rule của `EC_POLICY_V1` là so sánh số liệu/ngày tháng chính xác tuyệt đối; để LLM tự quyết định rủi ro làm sai kết quả chấm điểm (financial_resolution, evidence_ids bị hard-gate nếu sai). Tách LLM thành bước reasoning độc lập sau khi đã verify vừa đáp ứng yêu cầu về model, vừa không đánh đổi độ chính xác đã được test qua `test_person1/2/3.py`.
- **Bằng chứng quyết định phù hợp:** 50/50 case verifier PASS (đo thực tế từ `logging/trace.jsonl`, event `verification` với `is_valid: true` cho cả 50 case), trace có đủ 50 dòng `coordinator_llm.reasoning` với số liệu output không đổi so với trước bước LLM.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Trong lúc khởi tạo dự án, đã tạo nhầm `src/data_loader.py` và `src/agents/order_seller_agent.py` bản nháp trước khi phát hiện Người 1 đã có module thật cùng vị trí `src/agents/`, dẫn đến xung đột ghi đè tiềm ẩn.
- **Lệnh hoặc bước tái hiện:** Ghi file mới vào `src/agents/order_seller_agent.py` mà chưa đọc file hiện có.
- **Nguyên nhân gốc:** Không kiểm tra lại toàn bộ cây thư mục ngay trước khi ghi, trong khi các thành viên khác đang code song song trên cùng repo.
- **Cách xử lý:** Dừng lại, quét lại toàn bộ thư mục, đọc hết code thật của Người 1/2/3, bỏ hẳn logic nháp trùng lặp, viết `Coordinator` import trực tiếp module thật thay vì tự triển khai lại.
- **Cách xác minh sau khi sửa:** Đọc `src/coordinator.py` xác nhận chỉ import từ `src.agents.order_seller_agent`, `agents.payment_agent`, `agents.delivery_agent`, `agents.policy_agent`, `agents.verifier_agent` — không còn logic nghiệp vụ trùng lặp.
- **Điều học được:** Với repo nhóm chỉnh sửa song song, phải quét lại trạng thái thư mục ngay trước mỗi lần ghi file quan trọng, không giả định trạng thái đã biết từ đầu phiên vẫn còn đúng.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

Dữ liệu đi từ `input/EC_XXX.json` (chứa `claimed_order_id` và nội dung khiếu nại của khách) qua Coordinator, dùng `claimed_order_id` để Order & Seller Agent join 4 CSV (`orders`, `order_items`, `customers`, `sellers`) trong `data/`. Mỗi case được Coordinator điều phối tuần tự qua 5 agent: Order & Seller Agent trả về order/item/seller info; Payment Agent và Delivery Agent chạy song song dựa trên handoff đó (Payment đọc `order_payments`, Delivery so sánh timestamp giao hàng); Policy Agent gộp cả 3 handoff và áp `EC_POLICY_V1` theo đúng 6 rule ưu tiên để sinh output JSON; Verifier Agent kiểm schema, giới hạn số lượng entity/evidence, tính nhất quán case_status/refund trước khi output được coi là hợp lệ — đây là bước kiểm chất lượng duy nhất trước khi ghi `output/`. Coordinator LLM reasoning (Groq) chạy sau cùng, chỉ sinh `summary_vi`/`sanity_check_pass`, không có quyền ghi đè số liệu nên không ảnh hưởng đến correctness đã được Verifier xác nhận. Toàn bộ 50 case dùng chung 1 lần `DataLoader` nạp CSV và 1 bản `EC_POLICY_V1` để đảm bảo nhất quán giữa các case, và mỗi agent chỉ đọc đúng phạm vi dữ liệu được giao (không agent nào tự ý đọc CSV ngoài phạm vi mình phụ trách).

## 8. Cam kết của thành viên

- [X] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [X] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [X] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [X] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [X] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Hữu Hoàng A
**Ngày xác nhậ** 2026-08-05
