# Kế hoạch triển khai — Multi-Agent E-commerce Dispute Resolution

## 1. Mục tiêu

- Xử lý đầy đủ 50 file `input/EC_001.json` đến `input/EC_050.json`.
- Sinh 50 JSON tương ứng trong `output/`, đúng schema và quy tắc `EC_POLICY_V1`.
- Thể hiện kiến trúc multi-agent có phân vai, handoff, coordinator và verifier.
- Hoàn tất các artifact bắt buộc: `architecture.md`, báo cáo cá nhân, `logging/trace.jsonl`, `logging/metadata.json`.
- Zip thư mục `output/` chỉ gồm đúng 50 file JSON.

## 2. Phân công bốn thành viên

| Thành viên | Vai trò | Đầu ra chịu trách nhiệm |
| --- | --- | --- |
| Người 1 | Data & Order/Seller Agent | Nạp/join dữ liệu order-item-seller, xác định seller handoff trễ |
| Người 2 | Payment & Delivery Agent | Đối soát payment, xác định giao trễ hoặc đúng hạn |
| Người 3 | Policy & Output Verifier Agent | Áp dụng policy, sinh và xác thực output JSON |
| Người 4 | Coordinator, Integration & Documentation | Điều phối pipeline, batch 50 case, trace, tài liệu và đóng gói |

## 3. Người 1 — Data Engineer + Order/Seller Agent

### Công việc

- [ ] Khảo sát schema của 9 CSV trong `data/`.
- [ ] Xây dựng module load CSV một lần cho toàn bộ batch.
- [ ] Tra cứu `claimed_order_id` từ input.
- [ ] Join `orders`, `order_items`, `customers` và `sellers`.
- [ ] Trích xuất `order_status` và các timestamps: purchase, approved, carrier, delivered, estimated.
- [ ] Trích xuất mỗi item: `order_item_id`, `seller_id`, `shipping_limit_date`, `price`, `freight_value`.
- [ ] Xác định seller giao carrier muộn theo `order_delivered_carrier_date > shipping_limit_date`.
- [ ] Chuẩn hóa evidence: `order:<order_id>`, `item:<order_id>:<item_id>`, `seller:<seller_id>`.

### Handoff chuẩn

```json
{
  "order": {},
  "items": [],
  "seller_handoff_late": false,
  "violating_seller_ids": [],
  "item_total_brl": 0.0,
  "freight_total_brl": 0.0,
  "evidence_ids": []
}
```

### Tiêu chí hoàn thành

- [ ] Hoạt động đúng với order nhiều item hoặc seller.
- [ ] Tối đa 5 `item_ids` và 5 `seller_ids`.
- [ ] Không suy diễn sự kiện ngoài dữ liệu CSV.

## 4. Người 2 — Payment Agent + Delivery Agent

### Payment Agent

- [ ] Join `order_payments` theo `order_id`.
- [ ] Tính `payment_total_brl = sum(payment_value)`.
- [ ] Lấy payment theo `payment_sequential`.
- [ ] Kiểm tra split payment hợp lệ: có ít nhất 2 payment rows và `abs(payment_total - (item_total + freight_total)) <= 0.10`.
- [ ] Sinh evidence `payment:<order_id>:<payment_sequential>`.

### Delivery Agent

- [ ] So sánh `order_delivered_customer_date` với `order_estimated_delivery_date`.
- [ ] Xác định delivery late khi delivered date lớn hơn estimated date.
- [ ] Phân loại seller late nếu carrier nhận hàng sau shipping limit.
- [ ] Phân loại logistics late nếu seller bàn giao đúng hạn nhưng giao khách trễ.
- [ ] Xử lý an toàn timestamp thiếu cho order canceled/unavailable.

### Handoff chuẩn

```json
{
  "payment_rows": [],
  "payment_total_brl": 0.0,
  "has_valid_split_payment": false,
  "delivery_late": false,
  "delivery_within_estimate": false,
  "evidence_ids": []
}
```

### Tiêu chí hoàn thành

- [ ] Dùng tổng `payment_value`, không nhầm với số installments.
- [ ] Phân loại seller/logistics đúng quy tắc đề bài.
- [ ] Chỉ kết luận `unsupported_late_claim` khi payment khớp.

## 5. Người 3 — Policy Agent + Verifier Agent

### Policy Agent

- [ ] Nhận và tổng hợp handoff từ Người 1 và Người 2.
- [ ] Áp dụng rule theo đúng thứ tự ưu tiên:
  1. `canceled_order_paid`
  2. `unavailable_order_paid`
  3. `late_delivery_seller`
  4. `late_delivery_logistics`
  5. `valid_split_payment`
  6. `unsupported_late_claim`
- [ ] Gán đúng `primary_issue`, `case_status`, root-cause, responsible parties, refund và action.
- [ ] Hoàn payment toàn bộ cho canceled/unavailable.
- [ ] Hoàn tổng freight cho late seller/logistics.
- [ ] Gán hoàn tiền `0.0` cho split payment hợp lệ hoặc claim trễ không có cơ sở.
- [ ] Làm tròn toàn bộ số tiền đến hai chữ số thập phân.

### Verifier Agent

- [ ] Kiểm tra output theo schema README.
- [ ] Kiểm tra giới hạn entity/evidence/cause/party/action.
- [ ] Kiểm tra evidence ID đúng định dạng và tồn tại trong dữ liệu.
- [ ] Kiểm tra consistency: status, refund, responsible party và action phải phù hợp policy.
- [ ] Kiểm tra confidence thuộc đoạn `[0, 1]`.

### Tiêu chí hoàn thành

- [ ] Mỗi output là JSON hợp lệ.
- [ ] Không có evidence false positive.
- [ ] Có test cho toàn bộ 6 loại `primary_issue`.

## 6. Người 4 — Coordinator, Integration & Documentation

### Coordinator

- [ ] Thiết kế pipeline: load case → Order/Seller Agent → Payment/Delivery Agent → Policy Agent → Verifier Agent → ghi output.
- [ ] Đảm bảo logic được phân tách theo agent, không xử lý trong một prompt/hàm duy nhất.
- [ ] Ghi handoff và kết quả agent vào trace theo từng case.
- [ ] Điều phối batch xử lý 50 input.

### Tài liệu và submission

- [ ] Hoàn thiện `architecture.md`: sơ đồ agents, vai trò, quyền truy cập, handoff format và luồng xử lý.
- [ ] Hoàn thiện `individual_5SoCuoiMHV_HoVaTen.md`.
- [ ] Tạo `logging/metadata.json`: model, parameter size không quá 10B, framework và runtime.
- [ ] Tạo `logging/trace.jsonl` từ lần chạy mới nhất của đủ 50 case.
- [ ] Kiểm tra `output/` gồm đúng 50 JSON có tên khớp input.
- [ ] Nén riêng `output/`, không kèm source, `.env` hay log.

### Tiêu chí hoàn thành

- [ ] Pipeline chạy end-to-end không lỗi.
- [ ] Trace thể hiện agent execution và handoff cho cả 50 cases.
- [ ] File zip chỉ chứa `EC_001.json` đến `EC_050.json`.

## 7. Checklist tích hợp chung

### Trước khi chạy batch

- [ ] Chốt cấu trúc input/output giữa các agents.
- [ ] Chốt format handoff JSON.
- [ ] Chốt mapping policy → root cause → responsible party → refund → action.
- [ ] Test ít nhất một case cho mỗi primary issue.
- [ ] Khai báo model không quá 10B parameters trong source code.
- [ ] Đặt API key/secret trong `.env`, không commit.

### Khi chạy batch

- [ ] Dọn output cũ trước khi chạy để không còn file thừa.
- [ ] Chạy toàn bộ 50 input.
- [ ] Ghi đè trace, không append trace cũ.
- [ ] Thống kê số case theo `primary_issue`.
- [ ] Rà soát case confidence thấp và case có timestamp thiếu.

### Trước khi nộp

- [ ] `output/` có chính xác 50 file.
- [ ] Tất cả output parse được bằng JSON parser.
- [ ] Evidence IDs đúng format và tham chiếu dữ liệu tồn tại.
- [ ] Toàn bộ số tiền/refund được làm tròn hai chữ số thập phân.
- [ ] Có `architecture.md`, báo cáo cá nhân, `logging/metadata.json`, `logging/trace.jsonl`.
- [ ] Commit source code và tài liệu trước khi nộp.
- [ ] Zip chỉ thư mục `output/`.
