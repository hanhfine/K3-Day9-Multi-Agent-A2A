"""
Delivery Agent — Người 2
=========================
Kiểm tra thời gian giao hàng cho từng order:
- So sánh ngày giao thực tế với ngày dự kiến
- Phân loại: seller trễ, logistics trễ, hoặc giao đúng hạn
- Xử lý an toàn timestamp thiếu (order canceled/unavailable)
"""

from datetime import datetime
from typing import Any

# Model <= 10B declared in source code per README section 9.4
MODEL_NAME = "qwen2.5-10b-instruct"

SYSTEM_PROMPT = """
You are the Delivery Agent in a Multi-Agent E-commerce Dispute Resolution System.
Your responsibility:
- Compare order_delivered_customer_date against order_estimated_delivery_date.
- If delivered_customer > estimated_delivery -> delivery_late = True.
- If delivery_late: determine fault (seller_late vs logistics_late) by checking order_delivered_carrier_date against shipping_limit_date of each item.
- Safe handling of missing timestamps for canceled/unavailable orders.
"""


def _parse_timestamp(ts: str | None) -> datetime | None:
    """Parse timestamp từ CSV hoặc từ handoff của Order/Seller Agent. Trả về None
    nếu thiếu hoặc rỗng.

    Chấp nhận 2 định dạng:
      - Format gốc trong CSV: '2017-10-02 10:56:33'
      - Format ISO do OrderSellerAgent (Người 1) xuất ra khi JSON-hoá pd.Timestamp:
        '2017-10-02T10:56:33'
    """
    if isinstance(ts, datetime):
        return ts
    if not ts or not str(ts).strip() or str(ts).strip().strip('"') == "":
        return None
    ts_clean = str(ts).strip().strip('"')
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(ts_clean, fmt)
        except ValueError:
            continue
    return None


def run(order: dict, items: list[dict]) -> dict[str, Any]:
    """Chạy Delivery Agent cho 1 order.

    Args:
        order: dict chứa thông tin order từ orders CSV, bao gồm:
            - order_id
            - order_status
            - order_delivered_carrier_date
            - order_delivered_customer_date
            - order_estimated_delivery_date
        items: list[dict] chứa thông tin items từ order_items CSV, mỗi item có:
            - order_item_id
            - seller_id
            - shipping_limit_date
            - price
            - freight_value

    Returns:
        dict handoff theo format chuẩn trong plan.md
    """
    order_id = order.get("order_id", "")
    order_status = order.get("order_status", "").strip().strip('"')

    # Parse các timestamps
    delivered_customer = _parse_timestamp(order.get("order_delivered_customer_date"))
    estimated_delivery = _parse_timestamp(order.get("order_estimated_delivery_date"))
    delivered_carrier = _parse_timestamp(order.get("order_delivered_carrier_date"))

    # Mặc định: không trễ, không trong hạn (cho canceled/unavailable)
    delivery_late = False
    seller_late = False
    logistics_late = False
    delivery_within_estimate = False
    violating_seller_ids = []

    # Xử lý an toàn: order canceled hoặc unavailable thường thiếu timestamps
    if order_status in ("canceled", "unavailable"):
        # Không cần phân tích delivery cho order đã hủy/unavailable
        return {
            "delivery_late": False,
            "seller_late": False,
            "logistics_late": False,
            "delivery_within_estimate": False,
            "violating_seller_ids": [],
            "timestamps": {
                "delivered_customer": None,
                "estimated_delivery": None,
                "delivered_carrier": None,
            },
            "evidence_ids": [],
        }

    # Kiểm tra giao trễ: delivered_customer > estimated_delivery
    if delivered_customer and estimated_delivery:
        delivery_late = delivered_customer > estimated_delivery
        delivery_within_estimate = not delivery_late

    # Nếu giao trễ → phân loại seller hay logistics
    if delivery_late and delivered_carrier:
        # Kiểm tra từng item: carrier nhận hàng có sau shipping_limit_date không?
        any_seller_late = False
        for item in items:
            shipping_limit = _parse_timestamp(item.get("shipping_limit_date"))
            if shipping_limit and delivered_carrier > shipping_limit:
                any_seller_late = True
                seller_id = item.get("seller_id", "").strip().strip('"')
                if seller_id and seller_id not in violating_seller_ids:
                    violating_seller_ids.append(seller_id)

        if any_seller_late:
            # Seller bàn giao cho carrier SAU shipping_limit → lỗi seller
            seller_late = True
            logistics_late = False
        else:
            # Seller bàn giao đúng hạn nhưng vẫn giao trễ → lỗi logistics
            seller_late = False
            logistics_late = True

    return {
        "delivery_late": delivery_late,
        "seller_late": seller_late,
        "logistics_late": logistics_late,
        "delivery_within_estimate": delivery_within_estimate,
        "violating_seller_ids": violating_seller_ids[:5],  # Giới hạn tối đa 5
        "timestamps": {
            "delivered_customer": delivered_customer.isoformat() if delivered_customer else None,
            "estimated_delivery": estimated_delivery.isoformat() if estimated_delivery else None,
            "delivered_carrier": delivered_carrier.isoformat() if delivered_carrier else None,
        },
        "evidence_ids": [],  # Delivery Agent không sinh thêm evidence riêng
    }
