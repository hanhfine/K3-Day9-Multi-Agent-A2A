# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Hữu Hoàng Anh |
| MSSV | 2A202601357 |
| Khóa/Lớp | K3 |
| Vai trò chính | Người 2 — Payment Agent & Delivery Agent |
| Ngày hoàn thành | 2026-08-05 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Payment Agent | `agents/payment_agent.py` (`run()`) | `order_id`, `item_total_brl`, `freight_total_brl` | `pay_handoff` dict (payment_total, split status, payment evidence) | Hoàn thành |
| Delivery Agent | `agents/delivery_agent.py` (`run()`) | `order` dict, `items` list | `del_handoff` dict (delivery_late, seller_late, logistics_late) | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Test suite & Verification | Người 3 / Policy & Verifier Agent | Viết `test_person2.py` xác minh 50/50 cases qua Payment + Delivery Agent |
| Integration | Người 4 / Coordinator | Đảm bảo handoff contract tương thích hoàn toàn giữa Python CSV loader và Pandas loader |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Xây dựng Payment Agent | `agents/payment_agent.py` | Load caching `olist_order_payments_dataset.csv`, tính tổng `payment_value`, check split payment ±0.10 BRL | `python test_person2.py` |
| Xây dựng Delivery Agent | `agents/delivery_agent.py` | So sánh timestamps (`delivered_customer`, `estimated_delivery`, `shipping_limit_date`), phân loại seller late vs logistics late | `python test_person2.py` |
| Bàn giao Handoff schema | `agents/payment_agent.py`, `agents/delivery_agent.py` | Handoff chuẩn theo đúng định dạng `plan.md` | `python main.py` |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Khách hàng có thể phản ánh "giao trễ" hoặc "thanh toán trùng/nhiều dòng". Cần đối soát dữ liệu thực tế trong CSV để xác định chính xác:
1. Tổng tiền thanh toán thực sự có khớp với tổng giá trị item + phí vận chuyển không (Split payment hợp lệ).
2. Đơn hàng thực sự trễ do lỗi của Seller (bàn giao cho carrier sau `shipping_limit_date`) hay do Logistics Provider (giao cho khách sau `estimated_delivery_date` dù seller bàn giao đúng hạn).

### Cách triển khai
- **Payment Agent**:
  - Dùng `csv.DictReader` với in-memory caching để load `olist_order_payments_dataset.csv` một lần duy nhất cho cả 50 case batch.
  - Phân tích split payment hợp lệ khi `payment_count >= 2` và `abs(payment_total - (item_total + freight_total)) <= 0.10`.
  - Trích xuất evidence theo format: `payment:<order_id>:<payment_sequential>`.
- **Delivery Agent**:
  - Parse an toàn ISO timestamps trong dữ liệu.
  - Với đơn hàng `canceled` hoặc `unavailable`, tự động bỏ qua phân tích giao hàng.
  - Phân loại `seller_late = True` nếu `delivered_carrier > shipping_limit_date` của bất kỳ item nào. Nếu carrier nhận đúng hạn nhưng giao trễ thì `logistics_late = True`.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `order_id` (str), `order` (dict), `items` (list[dict]), `item_total_brl` (float), `freight_total_brl` (float) |
| Output | `pay_handoff` dict & `del_handoff` dict chứa flags, totals và evidence_ids |
| Module phụ thuộc | `src/agents/order_seller_agent.py` (Người 1) |
| Module sử dụng output | `agents/policy_agent.py` (Người 3) & `agents/verifier_agent.py` (Người 3) |
| Điều kiện lỗi cần xử lý | Missing timestamps, timestamp rỗng, order không tìm thấy payment row |

### Cách xác minh

```bash
python test_person2.py
python main.py
```

- **Kết quả mong đợi:** 50/50 cases chạy thành công, phân loại đúng 6 nhóm issue.
- **Kết quả thực tế:** Pass 50/50 cases, Verifier Agent báo 0 lỗi.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần xử lý batch 50 cases với tốc độ cao và đảm bảo tính chính xác tuyệt đối.
- **Các phương án đã cân nhắc:**
  1. Dùng pandas query CSV cho từng case.
  2. Cache toàn bộ `order_payments` vào dictionary ở memory ngay khi khởi tạo agent.
- **Phương án đã chọn:** Phương án 2 (In-memory Caching Dictionary).
- **Lý do:** Tăng tốc độ chạy batch 50 cases từ hơn 15 giây xuống chỉ còn ~1.1 giây.
- **Bằng chứng quyết định phù hợp:** Benchmark `main.py` hoàn thành 50 cases trong **1.187s**.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `UnicodeEncodeError: 'charmap' codec can't encode character '\u1eb1'` khi chạy test trên Windows console.
- **Lệnh hoặc bước tái hiện:** `python test_person2.py`
- **Nguyên nhân gốc:** Console mặc định của Windows (cp1252/cp936) không hỗ trợ ký tự Unicode tiếng Việt trong message của customer_request.
- **Cách xử lý:** Thêm `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")` ở đầu tất cả file script.
- **Cách xác minh sau khi sửa:** Chạy `python test_person2.py` hiển thị đầy đủ tiếng Việt không hề crash.

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ input đến output:** Input JSON chứa `claimed_order_id` -> Order/Seller Agent nạp order & items -> Payment Agent đối soát tiền -> Delivery Agent so sánh ngày giao -> Policy Agent áp rule `EC_POLICY_V1` -> Verifier Agent kiểm chứng schema/evidence -> Output JSON.
2. **Evaluation set & ground truth:** 50 case inputs mô phỏng khiếu nại thực tế, Verifier Agent đảm bảo không bị false positive hay hallucinate evidence ID.
3. **Multi-agent handoff:** Việc tách biệt domain làm tăng khả năng mở rộng (modularity), kiểm thử độc lập và tránh việc 1 prompt LLM ôm quá nhiều logic dẫn đến hallucination.

## 8. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Hữu Hoàng Anh  
**Ngày xác nhận:** 2026-08-05
