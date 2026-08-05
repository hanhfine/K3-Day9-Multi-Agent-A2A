"""
Payment Agent — Người 2
========================
Đối soát thanh toán cho từng order:
- Tính tổng payment_total_brl
- Đếm số payment rows
- Kiểm tra split payment hợp lệ
- Sinh evidence IDs cho payment
"""

import csv
import os
from typing import Any

# Model <= 10B declared in source code per README section 9.4
MODEL_NAME = "qwen2.5-10b-instruct"

SYSTEM_PROMPT = """
You are the Payment Agent in a Multi-Agent E-commerce Dispute Resolution System.
Your responsibility:
- Audit all payment rows for claimed_order_id.
- Calculate payment_total_brl = SUM(payment_value).
- Validate split payments (payment_count >= 2 and abs(payment_total - (item_total + freight_total)) <= 0.10).
- Extract evidence: payment:<order_id>:<payment_sequential>.
"""

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
PAYMENTS_CSV = os.path.join(DATA_DIR, "olist_order_payments_dataset.csv")

# Cache toàn bộ payments, group theo order_id (load 1 lần duy nhất)
_payments_cache: dict[str, list[dict]] | None = None


def _load_payments() -> dict[str, list[dict]]:
    """Load toàn bộ order_payments CSV, group theo order_id.
    Chỉ load 1 lần rồi cache lại cho cả batch 50 case.
    """
    global _payments_cache
    if _payments_cache is not None:
        return _payments_cache

    _payments_cache = {}
    with open(PAYMENTS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            oid = row["order_id"].strip().strip('"')
            _payments_cache.setdefault(oid, []).append({
                "payment_sequential": int(row["payment_sequential"]),
                "payment_type": row["payment_type"].strip().strip('"'),
                "payment_installments": int(row["payment_installments"]),
                "payment_value": float(row["payment_value"]),
            })

    # Sắp xếp theo payment_sequential trong mỗi order
    for oid in _payments_cache:
        _payments_cache[oid].sort(key=lambda x: x["payment_sequential"])

    return _payments_cache


def run(order_id: str, item_total_brl: float, freight_total_brl: float) -> dict[str, Any]:
    """Chạy Payment Agent cho 1 order.

    Args:
        order_id:        ID đơn hàng (claimed_order_id từ input)
        item_total_brl:  Tổng giá trị item (từ Order/Seller Agent - Người 1)
        freight_total_brl: Tổng phí vận chuyển (từ Order/Seller Agent - Người 1)

    Returns:
        dict handoff theo format chuẩn trong plan.md
    """
    payments_db = _load_payments()
    payment_rows = payments_db.get(order_id, [])

    # Tính tổng payment, làm tròn 2 chữ số thập phân
    payment_total = round(sum(p["payment_value"] for p in payment_rows), 2)

    # Kiểm tra split payment hợp lệ:
    #   - Có ít nhất 2 payment rows
    #   - abs(payment_total - (item_total + freight_total)) <= 0.10
    payment_count = len(payment_rows)
    expected_total = round(item_total_brl + freight_total_brl, 2)
    difference = abs(payment_total - expected_total)
    has_valid_split = payment_count >= 2 and difference <= 0.10

    # Sinh evidence IDs: payment:<order_id>:<payment_sequential>
    # Giới hạn tối đa 5 evidence (theo giới hạn entity set)
    evidence_ids = []
    for p in payment_rows[:5]:
        evidence_ids.append(f"payment:{order_id}:{p['payment_sequential']}")

    return {
        "payment_rows": payment_rows,
        "payment_count": payment_count,
        "payment_total_brl": payment_total,
        "has_valid_split_payment": has_valid_split,
        "payment_ids": [f"{order_id}:{p['payment_sequential']}" for p in payment_rows[:5]],
        "evidence_ids": evidence_ids,
    }
