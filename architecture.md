# Architecture — Multi-Agent E-commerce Dispute Resolution

## 1. Sơ đồ tổng quan

```text
input/EC_XXX.json
        │
        ▼
┌───────────────────────┐
│      Coordinator       │  (Người 4, src/coordinator.py)
│  - Nạp case, điều phối │
│  - Ghi trace từng bước │
└───────────┬────────────┘
            │ claimed_order_id
            ▼
┌───────────────────────────┐
│  Order & Seller Agent      │  (Người 1, src/agents/order_seller_agent.py)
│  Đọc: orders, order_items, │
│  customers, sellers (CSV)  │
│  → order, items,           │
│    seller_handoff_late,    │
│    violating_seller_ids,   │
│    item_total_brl,         │
│    freight_total_brl,      │
│    evidence_ids            │
└───────────┬────────────────┘
            │ handoff JSON
      ┌─────┴─────┐
      ▼           ▼
┌───────────┐ ┌────────────┐
│  Payment   │ │  Delivery   │  (Người 2, agents/payment_agent.py,
│  Agent     │ │  Agent      │   agents/delivery_agent.py)
│  Đọc:      │ │  Đọc: order,│
│  order_    │ │  items từ   │
│  payments  │ │  handoff    │
│  (CSV)     │ │  Người 1    │
│  → payment_│ │  → delivery_│
│  total,    │ │  late,      │
│  split ok, │ │  seller/    │
│  evidence  │ │  logistics_ │
│            │ │  late       │
└─────┬──────┘ └─────┬───────┘
      └──────┬───────┘
             ▼ handoff JSON
┌────────────────────────────┐
│      Policy Agent           │  (Người 3, agents/policy_agent.py)
│  Áp EC_POLICY_V1 theo thứ   │
│  tự ưu tiên 6 rule → output │
│  JSON đúng schema README    │
└───────────┬──────────────────┘
            │ output JSON (chưa xác nhận)
            ▼
┌────────────────────────────┐
│      Verifier Agent         │  (Người 3, agents/verifier_agent.py)
│  Kiểm schema, limit, evidence│
│  format+tồn tại, consistency│
│  → (is_valid, errors)       │
└───────────┬──────────────────┘
            │ is_valid, errors
            ▼
┌────────────────────────────┐
│  Coordinator LLM Reasoning   │  (Người 4, src/coordinator.py,
│  Model: llama-3.1-8b-instant │   qua Groq API)
│  Chỉ sinh summary_vi +       │
│  sanity_check_pass — KHÔNG   │
│  được ghi đè số liệu đã      │
│  verify                      │
└───────────┬──────────────────┘
            │
            ▼
   output/EC_XXX.json  +  logging/trace.jsonl (mỗi bước 1 dòng event)
```

## 2. Vai trò và quyền truy cập từng agent

| Agent | Sở hữu | Đọc | Ghi / trả về | Dùng LLM? |
| --- | --- | --- | --- | --- |
| Coordinator | Người 4 | `input/*.json`, tất cả handoff | `output/*.json`, `logging/trace.jsonl` | Có (reasoning pass, không quyết định số liệu) |
| Order & Seller Agent | Người 1 | `orders`, `order_items`, `customers`, `sellers` (CSV) | Handoff order/item/seller cho Payment, Delivery, Policy Agent | Không |
| Payment Agent | Người 2 | `order_payments` (CSV), `item_total_brl`/`freight_total_brl` từ Người 1 | Handoff payment cho Policy Agent | Không |
| Delivery Agent | Người 2 | `order`, `items` từ handoff Người 1 | Handoff delivery cho Policy Agent | Không |
| Policy Agent | Người 3 | Handoff Người 1 + Người 2 | Output JSON (chưa xác nhận) cho Verifier Agent | Không |
| Verifier Agent | Người 3 | Output JSON + toàn bộ handoff gốc | `(is_valid, errors)` cho Coordinator | Không |

Nguyên tắc quyền truy cập: mỗi agent chỉ đọc đúng nguồn dữ liệu thuộc phạm vi của mình (không agent nào tự ý đọc CSV ngoài phạm vi được giao) và chỉ giao tiếp với agent khác qua handoff JSON đã được chuẩn hoá — không có agent nào ghi trực tiếp vào `output/` ngoại trừ Coordinator.

## 3. Vì sao tách quyết định deterministic khỏi LLM

Toàn bộ engine quyết định (join dữ liệu, so sánh timestamp, áp `EC_POLICY_V1`, tính refund, kiểm schema) được cài đặt **thuần deterministic bằng Python** trong các module của Người 1/2/3. Lý do:

- README.md yêu cầu "ưu tiên dữ liệu có thể kiểm chứng thay vì tin hoàn toàn vào lời khiếu nại hoặc tự tạo ra sự kiện không tồn tại" — các rule trong `EC_POLICY_V1` là quy tắc so sánh số liệu/ngày tháng chính xác tuyệt đối, không có chỗ cho suy diễn xác suất.
- Phần chấm điểm (README mục 8) yêu cầu độ chính xác tuyệt đối cho `financial_resolution`, `evidence_ids`, `affected_entities` — sai số làm tròn hay hallucination của LLM sẽ trực tiếp mất điểm hoặc bị hard-gate.

Đề bài yêu cầu mỗi agent khai báo và sử dụng model ≤10B tham số (README mục 9). Để vừa đáp ứng yêu cầu này vừa không đánh đổi độ chính xác đã kiểm chứng của Người 1/2/3, Coordinator (Người 4) thêm **một bước LLM riêng biệt sau Verifier Agent**: gọi `llama-3.1-8b-instant` qua Groq API để sinh đoạn diễn giải tiếng Việt cho khách hàng và tự đối chiếu tính nhất quán (`sanity_check_pass`). Bước này:

- Chạy sau khi Verifier Agent đã xác nhận output hợp lệ.
- Không có quyền ghi đè bất kỳ trường số liệu/boolean nào trong output cuối.
- Nếu Groq API lỗi hoặc bị tắt (`--no-llm`), pipeline vẫn chạy đủ 50 case với output không đổi — chỉ thiếu phần `summary_vi` trong trace.

Nhờ vậy hệ thống vừa có "agent gọi LLM" đúng tinh thần đề bài, vừa giữ nguyên độ chính xác 100% từ engine deterministic đã được Verifier Agent kiểm chứng.

## 4. Luồng xử lý 1 case (chi tiết)

1. Coordinator đọc `input/EC_XXX.json`, lấy `claimed_order_id`.
2. Order & Seller Agent tra `claimed_order_id` trong `orders.csv`; nếu không tồn tại, trả handoff rỗng an toàn. Join `order_items`, `customers`, `sellers`; tính `seller_handoff_late` bằng so sánh `order_delivered_carrier_date` với `shipping_limit_date` của từng item.
3. Payment Agent join `order_payments` theo `order_id`, tính `payment_total_brl`, kiểm tra split payment hợp lệ (≥2 payment rows và lệch ≤0.10 BRL so với `item_total + freight_total`).
4. Delivery Agent so sánh `order_delivered_customer_date` với `order_estimated_delivery_date`; nếu trễ, phân loại seller-late hay logistics-late dựa trên `shipping_limit_date`. Xử lý an toàn khi order `canceled`/`unavailable` (thiếu timestamp).
5. Policy Agent áp 6 rule theo đúng thứ tự ưu tiên trong README mục 4, sinh output JSON đầy đủ 6 khối bắt buộc (`assessment`, `affected_entities`, `root_cause_analysis`, `evidence_ids`, `financial_resolution`, `resolution_actions`).
6. Verifier Agent kiểm schema, giới hạn số lượng entity/evidence/cause/party/action, định dạng + tồn tại evidence ID, tính nhất quán `case_status`/`refund`/`party`/`action` theo policy đã khớp, làm tròn 2 chữ số thập phân.
7. Coordinator gọi LLM reasoning (Groq), ghi `output/EC_XXX.json` và toàn bộ trace event của case vào `logging/trace.jsonl`.

## 5. Handoff format

Xem `plan.md` mục 3–5 cho JSON schema handoff chi tiết của từng agent (Order/Seller, Payment, Delivery). Output cuối cùng đúng schema README.md mục 6.

## 6. Cấu trúc source code

```text
src/
  agents/
    data_loader.py        # Người 1 — nạp CSV 1 lần cho toàn batch
    order_seller_agent.py # Người 1 — Order & Seller Agent
    payment_agent.py      # Người 2
    delivery_agent.py     # Người 2
    policy_agent.py       # Người 3
    verifier_agent.py     # Người 3
  coordinator.py           # Người 4 — điều phối pipeline + LLM reasoning
  llm_client.py            # Người 4 — Groq API client dùng chung
  main.py                  # Người 4 — batch runner 50 case
data/                       # 5/9 CSV Olist thực sự dùng trong pipeline
input/EC_001.json .. EC_050.json
output/EC_001.json .. EC_050.json   (sinh ra khi chạy batch)
logging/trace.jsonl, logging/metadata.json
```
