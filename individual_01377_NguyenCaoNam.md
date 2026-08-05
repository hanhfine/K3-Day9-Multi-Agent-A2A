# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                                             |
| ------------------ | ----------------------------------------------------- |
| Họ và tên       | Nguyễn Cao Nam                                       |
| MSSV               | 01377                                                 |
| Khóa/Lớp         | K3                                                    |
| Vai trò chính    | Người 1 — Data Engineer + Order/Seller Agent       |
| Ngày hoàn thành | 2026-08-05                                            |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable   | File/hàm phụ trách                                                             | Input nhận vào                                 | Output bàn giao                                                                  | Trạng thái |
| -------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------ | --------------------------------------------------------------------------------- | ------------ |
| Data Loader          | `src/agents/data_loader.py` (class `DataLoader`)                                  | 4 file CSV: `orders`, `order_items`, `customers`, `sellers` | Pandas DataFrames được cache trên memory, tự động parse kiểu `datetime` an toàn | Hoàn thành |
| Order/Seller Agent   | `src/agents/order_seller_agent.py` (class `OrderSellerAgent`)                    | `claimed_order_id` từ Coordinator                | Handoff JSON chứa `order`, `items`, `seller_handoff_late`, `item_total_brl`, `evidence_ids` | Hoàn thành |
| Local Testing        | `test_person1.py`                                                                 | Case mẫu (VD: EC_001)                          | Log ra console định dạng JSON chuẩn bị handoff cho Người 2 và 3                   | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                              | Thành viên/module được hỗ trợ | Kết quả                                                                                                                                                                                                                                                                                  |
| ----------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Xây dựng chuẩn Handoff JSON            | Người 2, Người 3                   | Xác định trước các schema đầu ra chung để Người 2 (Payment/Delivery) và Người 3 (Policy) có thể dùng chung dữ liệu `order` và `items` mà không cần tự parse lại từ CSV, giúp tăng tốc độ xử lý batch 50 cases.                                                           |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện                                                                                                         | File/hàm/artifact liên quan                 | Kết quả bàn giao                                                                    | Cách xác minh                                                  |
| ----------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- | -------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Xây dựng module nạp dữ liệu trung tâm                                                                                             | `src/agents/data_loader.py`                 | Method `get_order_data(order_id)` trả về object dictionary gom toàn bộ quan hệ data | Khởi tạo class `DataLoader` không bị lỗi bộ nhớ hay parsing    |
| Xác định trạng thái giao hàng chậm từ Seller                                                                                       | `src/agents/order_seller_agent.py`          | Biến bool `seller_handoff_late` và list `violating_seller_ids`                     | Chạy `python test_person1.py`, so sánh bằng mắt ngày tháng   |
| Tổng hợp và làm tròn giá trị item, vận chuyển; Giới hạn evidence (Max 5)                                                         | `src/agents/order_seller_agent.py`          | `item_total_brl`, `freight_total_brl` và mảng `evidence_ids` hợp lệ theo yêu cầu      | Output JSON của test có chứa đủ các trường và max 5 item/seller|

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

- Trong bộ dữ liệu Olist, một khiếu nại (case) chỉ cung cấp `claimed_order_id`. Từ ID này, hệ thống phải tra cứu chéo qua nhiều bảng (Orders, Items, Customers, Sellers) để lấy ngữ cảnh. Việc đọc file CSV từ ổ cứng cho mỗi case sẽ vô cùng chậm khi chạy batch 50 case. 
- Thứ hai, định dạng thời gian trong CSV là chuỗi, nếu truyền thẳng qua JSON handoff sẽ dễ gây lỗi khi các Agent khác so sánh ngày tháng, hoặc sinh lỗi `NaT` (Not a Time) khi timestamp bị khuyết (đơn hàng bị hủy).

### Cách triển khai

- **`DataLoader`**: Tôi dùng thư viện `pandas` nạp 4 file CSV vào memory ngay từ đầu `__init__`. Mọi trường ngày tháng (vd: `order_purchase_timestamp`, `order_delivered_carrier_date`, `shipping_limit_date`) đều được ép kiểu qua `pd.to_datetime(..., errors='coerce')`. Điều này đảm bảo dữ liệu thời gian thống nhất.
- **`OrderSellerAgent`**: Agent này nhận `data_loader`, tra cứu `claimed_order_id`. Nó duyệt qua từng `item` của đơn, cộng dồn giá tiền (`price`) và phí ship (`freight_value`) thành `item_total_brl` và `freight_total_brl`. 
- Logic xác định `seller_handoff_late`: Nếu `order_delivered_carrier_date` (ngày vận chuyển lấy hàng) lớn hơn `shipping_limit_date` (hạn chót phải giao), thì người bán đó bị gán nhãn `seller_handoff_late = True`, ID người bán được đưa vào `violating_seller_ids`.
- Giới hạn Evidence: Tôi chủ động cắt mảng `evidence_ids.extend(item_evidences[:5])` để đảm bảo hệ thống không vi phạm điều kiện "tối đa 5 item_ids" từ README.

### Cách xác minh

```bash
python test_person1.py
```
- **Kết quả mong đợi:** In ra console quá trình loading CSV (Loading CSV files into memory...), tiếp theo in ra cấu trúc JSON của order. JSON không được chứa object `NaT` hay `Timestamp` rác của pandas. `seller_handoff_late` hiển thị `True` hoặc `False`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Khi lấy dữ liệu ngày tháng ra khỏi pandas, object trả về là kiểu `pd.Timestamp`. Kiểu dữ liệu này không thể serialize trực tiếp thành JSON chuẩn qua thư viện `json.dumps`, dẫn đến lỗi pipeline khi đưa dữ liệu (handoff) cho Người 2 và Người 3.
- **Phương án 1:** Ép kiểu datetime về chuỗi ngay trong `DataLoader`. Điều này làm hỏng mục đích xử lý/tính toán ngày tháng nội bộ bằng pandas.
- **Phương án 2 (Đã chọn):** Giữ nguyên `pd.Timestamp` trong `DataLoader` để tiện bề so sánh `>`, `<` (kiểm tra đi trễ). Chỉ đến bước trả kết quả handoff cuối cùng tại `OrderSellerAgent` (`safe_order` và `safe_items`), tôi mới dùng vòng lặp dò tìm: Nếu biến là `pd.Timestamp` thì gọi `.isoformat()`, nếu là `pd.isna(v)` thì chuyển thành `None`.
- **Lý do:** Cách này vừa đảm bảo logic so sánh thời gian cực kỳ mạnh mẽ của pandas (so sánh `carrier_date > limit_date`), vừa tuân thủ đúng định dạng JSON an toàn và minh bạch cho các Agent tuyến sau.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Lỗi `TypeError: Object of type Timestamp is not JSON serializable` khi cố in kết quả ra bằng hàm `json.dumps()` ở file `test_person1.py`. Hơn nữa là gặp lỗi `NaT is not JSON serializable` ở những đơn hàng trạng thái `canceled` do thiếu thời gian giao hàng.
- **Nguyên nhân gốc:** Pandas đại diện cho giá trị ngày tháng trống (missing) bằng `NaT` (Not a Time), và Python `json` library mặc định không biết cách parse 2 loại object chuyên biệt này của pandas.
- **Cách xử lý:** Tôi viết một khối kiểm tra thủ công trong vòng lặp parse output ở `order_seller_agent.py`: `if pd.isna(v): safe_order[k] = None; elif isinstance(v, pd.Timestamp): safe_order[k] = v.isoformat()`. Điều này giải quyết triệt để vấn đề `NaT` và ép kiểu chuẩn `ISO-8601`.
- **Điều học được:** Khi làm việc trong hệ thống Multi-Agent có handoff bằng dạng dữ liệu chuẩn (JSON), mọi biên giới giao tiếp đều phải được tiệt trùng (sanitize). Không bao giờ được vứt trực tiếp các object đặc thù của thư viện (như Dataframe, Series, Timestamp) sang cho Agent khác.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

Với tư cách là Người 1 phụ trách Data, tôi thấy luồng dữ liệu bắt đầu từ file `input/EC_XXX.json`. `Coordinator` đọc khiếu nại của khách, trích xuất `claimed_order_id` và đưa ngay cho `OrderSellerAgent` của tôi. Agent của tôi sẽ vét sạch thông tin trong 4 file CSV (nhờ `DataLoader`), lọc ra các timestamp, số tiền tổng hợp của item, phí ship và xác định xem Seller có đưa hàng chậm cho Shipper không.
Toàn bộ dữ liệu sạch này được đóng gói thành một cụm Handoff JSON duy nhất. Cụm này sẽ được Người 2 (Payment & Delivery) tái sử dụng hoàn toàn để so sánh thời gian giao đến khách, đối soát tiền trả. Sau cùng, mọi nhận định của Người 1 (như `seller_handoff_late`) và Người 2 sẽ dồn về cho Policy Agent (Người 3) áp luật 1 cách máy móc. Toàn bộ tính toán này chạy bằng Python thuần, và LLM của Coordinator chỉ vào xem kết quả ở phút thứ 89 để gõ vài câu chém gió tóm tắt tiếng Việt. Kiến trúc này triệt tiêu hoàn toàn khả năng AI "ngáo" làm tính sai tiền refund.

## 8. Cam kết của thành viên

- [X] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [X] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [X] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [X] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [X] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Cao Nam
**Ngày xác nhận:** 2026-08-05
