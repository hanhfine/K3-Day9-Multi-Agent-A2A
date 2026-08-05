# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                  |
| --------------- | ------------------------------------------ |
| Họ và tên       | Nguyễn Phương Nam                          |
| MSSV            | 2A202601952                                |
| Khóa/Lớp        | K3                                         |
| Vai trò chính   | Người 3 — Policy Agent & Verifier Agent    |
| Ngày hoàn thành | 2026-08-05                                 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable                        | File/hàm phụ trách                              | Input nhận vào                                                                 | Output bàn giao                                                    | Trạng thái |
| ------------------------------------------ | ------------------------------------------------ | -------------------------------------------------------------------------------- | --------------------------------------------------------------------- | ------------ |
| Policy Agent                                | `agents/policy_agent.py` (hàm `evaluate`)       | Handoff Order/Seller (Người 1) + Payment/Delivery (Người 2)                    | Output JSON đúng schema README mục 6 (chưa xác nhận)                | Hoàn thành |
| Verifier Agent                              | `agents/verifier_agent.py` (hàm `verify`)       | Output JSON từ Policy Agent + handoff gốc của Người 1/2                     | `(is_valid, errors)`                                                | Hoàn thành |
| Test tích hợp Người 1 → Người 2 → Người 3 | `test_person3.py`                               | 50 case `input/EC_XXX.json`                                                    | Thống kê `primary_issue`, `output/EC_XXX.json`, log PASS/FAIL   | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                                                                | Thành viên/module được hỗ trợ | Kết quả                                                                                                                                                                                     |
| -------------------------------------------------------------------------- | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Sửa `_parse_timestamp` trong `agents/delivery_agent.py`                  | Người 2 — Delivery Agent           | Phát hiện lúc nối pipeline thật: `OrderSellerAgent` (Người 1) xuất timestamp dạng ISO (`...T...`) nhưng `delivery_agent` chỉ parse được định dạng CSV gốc (`... ...`), sửa để chấp nhận cả 2 định dạng, không sửa logic nghiệp vụ của Người 2. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện                                                                     | File/hàm/artifact liên quan  | Kết quả bàn giao                                     | Cách xác minh          |
| -------------------------------------------------------------------------------------------- | ------------------------------ | -------------------------------------------------------- | ------------------------ |
| Áp `EC_POLICY_V1` đúng thứ tự ưu tiên 6 rule, sinh output JSON đủ 6 khối bắt buộc         | `agents/policy_agent.py`     | `output/EC_001.json`..`EC_050.json`                   | `python test_person3.py` |
| Kiểm schema, giới hạn số lượng, evidence, consistency trước khi output được coi là hợp lệ | `agents/verifier_agent.py`   | `(is_valid, errors)` cho mỗi case                     | `python test_person3.py` |
| Nối pipeline 3 người, chạy đủ 50/50 case, thống kê `primary_issue`                      | `test_person3.py`            | Log thống kê console + `output/` đầy đủ            | `python test_person3.py` |

Một output cụ thể: chạy `python test_person3.py` in ra thống kê 6 loại `primary_issue` trên 50 case: `canceled_order_paid` 8, `unavailable_order_paid` 8, `late_delivery_seller` 8, `late_delivery_logistics` 8, `valid_split_payment` 9, `unsupported_late_claim` 9 (tổng 50), và dòng `Verifier Agent: 50/50 case hợp lệ, 0 lỗi tổng cộng` (thực đo từ lần chạy thật).

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Sau khi Người 1 (Order/Seller) và Người 2 (Payment/Delivery) đã có handoff riêng lẻ, cần một agent áp `EC_POLICY_V1` đúng thứ tự ưu tiên 6 rule để ra quyết định cuối (`primary_issue`, `responsible party`, `refund`, `action`), và một agent độc lập kiểm tra output đó trước khi được coi là hợp lệ để ghi ra `output/` — tránh trường hợp Policy Agent tự sai (evidence không tồn tại, refund không khớp rule, vượt giới hạn số lượng) mà không ai phát hiện trước khi nộp bài.

### Cách triển khai

`policy_agent.evaluate()` nhận 3 handoff (`order_seller`, `payment`, `delivery`), áp lần lượt 6 rule theo đúng thứ tự ưu tiên README mục 4 (`canceled_order_paid` → `unavailable_order_paid` → `late_delivery_seller` → `late_delivery_logistics` → `valid_split_payment` → `unsupported_late_claim` làm fallback), dùng hàm nội bộ `_build_evidence` để chỉ gộp evidence thật sự liên quan trực tiếp đến rule đã khớp (không gộp bừa mọi evidence Người 1/2 đưa lên, tránh false positive), luôn cắt theo giới hạn `MAX_EVIDENCE`/`MAX_ENTITY`/`MAX_CAUSES`/`MAX_PARTIES`/`MAX_ACTIONS` trước khi trả về.

`verifier_agent.verify()` độc lập dựng lại "universe" evidence hợp lệ trực tiếp từ dữ liệu gốc của Người 1/2 (`_evidence_universe`, không tin dữ liệu Policy Agent tự khai), đối chiếu format từng evidence bằng regex theo prefix (`order:`/`item:`/`payment:`/`seller:`/`policy:`), rồi kiểm consistency chéo — `case_status`, `resolution_actions`, `recommended_refund_brl`, `responsible_parties.party_type` phải khớp đúng bảng ánh xạ theo `primary_issue` (`STATUS_BY_ISSUE`, `ACTION_BY_ISSUE`, `PARTY_TYPE_BY_ISSUE`) — để bắt lỗi logic nghiệp vụ chứ không chỉ lỗi schema.

### Input, output và contract

| Thành phần                   | Mô tả                                                                                                                                 |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Input                          | Handoff `order_seller` (Người 1), `payment` + `delivery` (Người 2) — dict Python theo contract đã thống nhất giữa 3 người        |
| Output                         | `output/EC_XXX.json` đúng schema README mục 6, cặp `(is_valid, errors)` từ Verifier Agent                                          |
| Module phụ thuộc              | `src/agents/order_seller_agent.py` (Người 1), `agents/payment_agent.py`, `agents/delivery_agent.py` (Người 2)                     |
| Module sử dụng output          | `src/coordinator.py` (Người 4) — ghi output đã verify vào `output/` và trace                                                    |
| Điều kiện lỗi cần xử lý    | Evidence ID sai định dạng hoặc không tồn tại trong dữ liệu (false positive); `case_status`/`action`/`refund`/`party` không khớp policy đã chọn; số lượng entity/evidence/cause/party/action vượt giới hạn README |

### Cách xác minh

```bash
python test_person3.py
```

- **Kết quả mong đợi:** đủ 6 loại `primary_issue` trên 50 case, Verifier PASS 50/50, 0 lỗi.
- **Kết quả thực tế:** chạy thành công, thống kê `canceled_order_paid` 8, `unavailable_order_paid` 8, `late_delivery_seller` 8, `late_delivery_logistics` 8, `valid_split_payment` 9, `unsupported_late_claim` 9 (tổng 50 case); `Verifier Agent: 50/50 case hợp lệ, 0 lỗi tổng cộng`; không có case confidence thấp cảnh báo.
- **Artifact/log:** `output/EC_001.json`..`EC_050.json`, log console của `test_person3.py`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Verifier Agent cần biết evidence ID nào là "thật" để chống Policy Agent tự bịa hoặc ghép nhầm evidence không tồn tại trong dữ liệu (false positive) — README yêu cầu ưu tiên dữ liệu có thể kiểm chứng thay vì tự tạo sự kiện không tồn tại.
- **Các phương án đã cân nhắc:**
  1. Verifier chỉ kiểm định dạng regex của evidence ID, không đối chiếu lại dữ liệu gốc.
  2. Verifier tự dựng lại tập evidence hợp lệ trực tiếp từ handoff gốc của Người 1/2 (`_evidence_universe`), rồi bắt buộc từng evidence Policy Agent trả về phải nằm trong tập đó.
- **Phương án đã chọn:** Phương án 2.
- **Lý do:** Phương án 1 chỉ bắt lỗi cú pháp, không bắt được trường hợp Policy Agent ghép nhầm evidence của order/seller khác hoặc tự sinh evidence không có thật — đây là loại lỗi bị hard-gate theo thang điểm README mục 8 (Evidence IDs 15%). Phương án 2 tốn thêm một bước dựng set từ dữ liệu gốc nhưng đảm bảo mọi evidence lọt qua Verifier chắc chắn dựng được từ CSV thật.
- **Bằng chứng quyết định phù hợp:** Chạy `test_person3.py` trên 50/50 case, 0 lỗi loại "Evidence false positive" và 0 lỗi "Evidence sai định dạng" trong toàn bộ log.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Khi nối pipeline thật (`test_person3.py`) chạy Người 1 → Người 2 → Người 3, `delivery_agent.run()` trả `delivery_late=False` cho toàn bộ case dù dữ liệu CSV cho thấy nhiều đơn giao trễ rõ ràng, khiến `late_delivery_seller`/`late_delivery_logistics` không bao giờ xuất hiện.
- **Lệnh hoặc bước tái hiện:** Chạy `test_person3.py` với handoff thật từ `OrderSellerAgent.process()` (Người 1) thay vì dict giả lập trong test riêng của Người 2.
- **Nguyên nhân gốc:** `OrderSellerAgent` (Người 1) JSON-hoá `pd.Timestamp` thành chuỗi ISO dạng `'YYYY-MM-DDTHH:MM:SS'`, trong khi `delivery_agent._parse_timestamp` (Người 2) chỉ parse đúng định dạng CSV gốc `'YYYY-MM-DD HH:MM:SS'` (dấu cách thay vì `T`), khiến mọi lần `strptime` raise `ValueError` và hàm trả về `None` cho mọi timestamp — bug chỉ lộ ra khi 2 module thật được ghép, không xuất hiện khi mỗi người test riêng lẻ với dữ liệu giả lập của mình.
- **Cách xử lý:** Sửa `_parse_timestamp` trong `agents/delivery_agent.py` để thử lần lượt 2 format (`"%Y-%m-%d %H:%M:%S"` và `"%Y-%m-%dT%H:%M:%S"`), không sửa gì trong module của Người 1.
- **Cách xác minh sau khi sửa:** Chạy lại `test_person3.py`, `delivery_late`/`seller_late`/`logistics_late` trả đúng giá trị khớp dữ liệu thật, đủ `late_delivery_seller` (8 case) và `late_delivery_logistics` (8 case) thay vì 0 case như trước khi sửa.
- **Điều học được:** Phải test bằng dữ liệu thật đi qua đủ chuỗi handoff giữa các module của người khác, không chỉ test module của mình với input giả lập, vì format dữ liệu qua ranh giới module (đặc biệt kiểu ngày giờ) dễ lệch nhau âm thầm mà không lỗi ngay.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

Dữ liệu đi từ `input/EC_XXX.json` (chứa `claimed_order_id`) qua Coordinator (Người 4) tới Order & Seller Agent (Người 1), agent này join `orders`, `order_items`, `customers`, `sellers` trong `data/` theo `claimed_order_id` để trả `order`, `items`, `seller_handoff_late`, `item_total_brl`, `freight_total_brl` và evidence gốc. Payment Agent và Delivery Agent (Người 2) chạy dựa trên handoff đó: Payment Agent đối soát `order_payments` với tổng item+freight để xác định split payment hợp lệ; Delivery Agent so sánh `order_delivered_carrier_date`/`order_delivered_customer_date` với `shipping_limit_date`/`order_estimated_delivery_date` để phân loại giao trễ do seller hay do logistics. Phần việc của tôi (Người 3) nhận cả 3 handoff này: Policy Agent áp đúng thứ tự ưu tiên 6 rule của `EC_POLICY_V1` để chọn `primary_issue` duy nhất, sinh output JSON đủ 6 khối theo schema README; Verifier Agent sau đó kiểm độc lập — schema, giới hạn số lượng, format và sự tồn tại thật của evidence ID, cùng tính nhất quán giữa `case_status`/`refund`/`responsible_parties`/`resolution_actions` với `primary_issue` đã chọn — đây là bước kiểm chất lượng cuối cùng trước khi Coordinator được phép ghi `output/EC_XXX.json`. Nếu Verifier phát hiện lỗi, case đó không được ghi output hợp lệ, buộc phải sửa lại Policy Agent chứ không được bỏ qua. Toàn bộ 50 case dùng chung 1 bản `EC_POLICY_V1` và 1 tập rule ưu tiên cố định để đảm bảo cùng dữ liệu đầu vào luôn cho cùng kết quả.

## 8. Cam kết của thành viên

- [X] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [X] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [X] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [X] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [X] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Phương Nam
**Ngày xác nhận:** 2026-08-05
