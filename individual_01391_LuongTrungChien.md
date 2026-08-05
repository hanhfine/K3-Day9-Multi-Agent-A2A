# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                       |
| --------------- | ----------------------------------------------- |
| Họ và tên       | Lương Trung Chiến                               |
| MSSV            | 2A202601391                                     |
| Khóa/Lớp        | K3                                              |
| Vai trò chính   | Người 2 — Payment Agent & Delivery Agent       |
| Ngày hoàn thành | 05/08/2026                                      |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Payment Agent | `agents/payment_agent.py` (`run()`) | `order_id` (str), `item_total_brl` (float), `freight_total_brl` (float) từ Người 1 | `pay_handoff` dict (`payment_rows`, `payment_total_brl`, `has_valid_split_payment`, `payment_ids`, `evidence_ids`) | Hoàn thành |
| Delivery Agent | `agents/delivery_agent.py` (`run()`) | `order` dict, `items` list từ Người 1 | `del_handoff` dict (`delivery_late`, `seller_late`, `logistics_late`, `delivery_within_estimate`, `violating_seller_ids`, `evidence_ids`) | Hoàn thành |
| Local Testing Suite | `test_person2.py` | 50 case input & CSV data | Log xác minh chi tiết kết quả chạy độc lập của 2 Agents cho 50 case | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Sửa lỗi `_parse_timestamp` chấp nhận định dạng ISO | Người 3 (`agents/policy_agent.py`, `agents/verifier_agent.py`) | Hỗ trợ tương thích timestamp dạng ISO (`...T...`) từ `OrderSellerAgent` (Người 1) xuất ra và dạng CSV gốc (`... ...`), tránh bug parse thành `None` khi tích hợp thật. |
| Rà soát interface Handoff Contract với Người 1 và Người 4 | Người 1 (`OrderSellerAgent`), Người 4 (`CoordinatorAgent`) | Đảm bảo `payment_agent` và `delivery_agent` truyền nhận đúng schema handoff chuẩn trong `plan.md`, cho phép Coordinator điều phối pipeline tuần tự mà không bị xung đột kiểu dữ liệu. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Xây dựng Payment Agent (Đối soát thanh toán & Split Payment) | `agents/payment_agent.py` | Caching in-memory `olist_order_payments_dataset.csv`, tính tổng `payment_value`, xác định split payment hợp lệ (`payment_count >= 2` và `abs(payment_total - (item_total + freight_total)) <= 0.10`) | `python test_person2.py` |
| Xây dựng Delivery Agent (Phân tích mốc thời gian giao hàng) | `agents/delivery_agent.py` | Parse an toàn timestamps ISO/CSV, phân loại `seller_late` (`delivered_carrier > shipping_limit`) vs `logistics_late` (`delivered_customer > estimated_delivery`), xử lý an toàn cho đơn hàng `canceled`/`unavailable` | `python test_person2.py` |
| Bàn giao Handoff schema chuẩn | `agents/payment_agent.py`, `agents/delivery_agent.py` | Handoff chuẩn theo đúng định dạng `plan.md` giao tiếp mượt mà với Policy Agent (Người 3) | `python main.py` |

Một output cụ thể: Chạy `python test_person2.py` in ra kết quả phân loại đối soát thanh toán và thời gian giao hàng thành công trên 50/50 cases, kết hợp cùng toàn bộ pipeline `main.py` đạt **50/50 cases Verifier Agent PASS (0 lỗi)**, đóng góp trực tiếp đưa kết quả toàn nhóm bứt phá đạt **95.8713 điểm** trên Leaderboard.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Một khiếu nại thương mại điện tử không thể giải quyết chỉ từ lời khai của khách hàng. Cần đối soát dữ liệu thực tế từ CSV Olist (`olist_order_payments_dataset.csv`, `olist_orders_dataset.csv`, `olist_order_items_dataset.csv`) để xác định 2 câu hỏi cốt lõi:
1. **Đối soát thanh toán**: Tổng tiền thanh toán thực sự có khớp với tổng giá trị item + phí vận chuyển không? Đơn hàng có thanh toán split payment hợp lệ hay không?
2. **Phân định trách nhiệm giao trễ**: Đơn hàng thực sự trễ do lỗi của Seller (bàn giao cho đơn vị vận chuyển sau `shipping_limit_date`) hay do Đơn vị vận chuyển / Logistics Provider (bàn giao cho khách hàng sau `estimated_delivery_date` dù Seller đã giao đúng hạn)?

### Cách triển khai

- **Payment Agent (`agents/payment_agent.py`)**:
  - Khởi tạo in-memory dictionary caching cho `olist_order_payments_dataset.csv` ngay từ lần gọi đầu tiên để phục vụ xử lý siêu tốc cho toàn bộ 50 cases.
  - Gom các dòng thanh toán theo `order_id`, lấy `payment_sequential` và cộng tổng `payment_value` (không nhầm lẫn với số đợt trả góp `payment_installments`).
  - Kiểm tra điều kiện Split Payment hợp lệ: `payment_count >= 2` và `abs(payment_total - (item_total + freight_total)) <= 0.10` BRL.
  - Chuẩn hóa evidence IDs theo đúng quy định README mục 5: `payment:<order_id>:<payment_sequential>`.

- **Delivery Agent (`agents/delivery_agent.py`)**:
  - Xây dựng hàm `_parse_timestamp` xử lý linh hoạt cả định dạng ISO (`2018-10-18T00:00:00-03:00`) lẫn định dạng CSV gốc (`2018-10-18 00:00:00`).
  - Xử lý an toàn cho các đơn hàng `canceled` hoặc `unavailable` (khi timestamps bị khuyết/NULL) mà không gây crash pipeline.
  - Phân định nguyên nhân giao trễ:
    - `seller_late = True`: Khi `order_delivered_carrier_date > shipping_limit_date` của item thuộc seller đó.
    - `logistics_late = True`: Khi seller bàn giao đúng hạn (`order_delivered_carrier_date <= shipping_limit_date`) nhưng carrier giao cho khách trễ (`order_delivered_customer_date > order_estimated_delivery_date`).
    - `delivery_within_estimate = True`: Khi đơn hàng được giao tới khách đúng hoặc trước thời hạn dự kiến.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `order_id` (str), `order` (dict), `items` (list[dict]), `item_total_brl` (float), `freight_total_brl` (float) từ `OrderSellerAgent` (Người 1) |
| Output | `pay_handoff` dict & `del_handoff` dict chứa flags, totals và evidence_ids chuẩn hóa |
| Module phụ thuộc | `src/agents/order_seller_agent.py` (Người 1 — Order/Seller Agent) |
| Module sử dụng output | `agents/policy_agent.py` (Người 3 — Policy Agent) & `agents/verifier_agent.py` (Người 3 — Verifier Agent) |
| Điều kiện lỗi cần xử lý | Timestamps bị khuyết (NULL), timestamp rỗng, order không tìm thấy payment row trong CSV, đơn bị hủy |

### Cách xác minh

```bash
python test_person2.py
python main.py
```

- **Kết quả mong đợi:** 50/50 cases xử lý thành công, phân loại đúng 6 nhóm issue, không bị rò rỉ hay dính lỗi parse timestamp.
- **Kết quả thực tế:** Verifier Agent PASS 50/50 cases (0 lỗi), kết quả toàn hệ thống đạt đỉnh điểm **95.8713 điểm**.
- **Artifact/log:** `output/`, `logging/trace.jsonl`, `logging/metadata.json`, `architecture.md`, `output.zip`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Khi xử lý batch 50 cases, việc mở và đọc lại file `olist_order_payments_dataset.csv` từ đĩa cho từng case khiến thời gian thực thi bị kéo dài.
- **Các phương án đã cân nhắc:**
  1. Đọc lại file CSV hoặc query qua Pandas cho từng case.
  2. Xây dựng cấu trúc in-memory lookup dictionary dạng `{order_id: [payment_rows]}` ngay từ lần nạp đầu tiên.
- **Phương án đã chọn:** Phương án 2 (In-Memory Lookup Caching Dictionary).
- **Lý do:** Giảm thời gian truy vấn dữ liệu thanh toán từ O(N) xuống O(1) cho mỗi case, giúp toàn bộ pipeline 50 cases chạy hoàn tất chỉ trong **~1.2 giây**.
- **Bằng chứng quyết định phù hợp:** Benchmark `main.py` hoàn thành batch 50 cases trong **1.218s**, đảm bảo hệ thống phản hồi siêu tốc.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `TypeError: '>' not supported between instances of 'NoneType' and 'datetime'` hoặc `ValueError` khi so sánh các mốc thời gian giao hàng đối với các đơn bị hủy (`canceled`) hoặc không có sẵn (`unavailable`).
- **Lệnh hoặc bước tái hiện:** Chạy test case đối với đơn hàng `EC_005` hoặc `EC_011` (đơn canceled/unavailable có timestamps bị rỗng).
- **Nguyên nhân gốc:** Các đơn hàng hủy hoặc không có hàng thì `order_delivered_carrier_date` hoặc `order_delivered_customer_date` trong CSV có giá trị `None`/Rỗng. Việc so sánh trực tiếp các đối tượng `datetime` với `None` gây ra lỗi crash chương trình.
- **Cách xử lý:** Thêm kiểm tra điều kiện an toàn `if not delivered_customer or not estimated_delivery: return {"delivery_late": False, ...}` trước khi thực hiện các phép so sánh thời gian.
- **Cách xác minh sau khi sửa:** Chạy `python main.py` hoàn thành 100% 50 cases bao gồm tất cả 16 cases `canceled` và `unavailable` mà không hề gặp lỗi.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

Dữ liệu bắt đầu từ `input/EC_XXX.json` lấy mã `claimed_order_id` để tra cứu và join thông tin từ các file CSV Olist trong `data/`. Luồng xử lý Multi-Agent trải qua 4 bước:
1. `OrderSellerAgent` (Người 1): Nạp dữ liệu đơn hàng, danh sách sản phẩm, giá tiền và phát hiện người bán bàn giao trễ so me với `shipping_limit_date`.
2. `PaymentAgent` & `DeliveryAgent` (Người 2 - Vai trò của tôi): Đối soát tổng tiền thanh toán (`payment_value`) với tổng tiền hàng + cước vận chuyển (kiểm tra split payment ±0.10 BRL) và phân tích chính xác mốc thời gian giao hàng (`delivery_late`, `seller_late`, `logistics_late`).
3. `PolicyAgent` & `VerifierAgent` (Người 3): Áp dụng chính sách `EC_POLICY_V1` theo thứ tự ưu tiên 6 cấp (`canceled_order_paid` -> `unavailable_order_paid` -> `late_delivery_seller` -> `late_delivery_logistics` -> `valid_split_payment` -> `unsupported_late_claim`) để đưa ra phán quyết, tính tiền hoàn `recommended_refund_brl`, xác định bên chịu trách nhiệm và hành động xử lý. `VerifierAgent` tự động kiểm định 6 lớp quy tắc kiểm soát chất lượng trước khi chấp nhận output.
4. `CoordinatorAgent` (Người 4): Điều phối tuần tự pipeline, ghi vết suy luận vào `trace.jsonl`, cập nhật `metadata.json` (mô hình `qwen2.5-10b-instruct` 10B) và đóng gói thư mục `output.zip` sẵn sàng nộp bài.

## 8. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Lương Trung Chiến  
**Ngày xác nhận:** 05/08/2026
