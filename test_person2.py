"""
Test script cho Payment Agent và Delivery Agent (Người 2)
==========================================================
Chạy:  python test_person2.py
"""

import json
import csv
import os
import sys
import io

# Fix Windows console encoding for Vietnamese
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Thêm project root vào path
sys.path.insert(0, os.path.dirname(__file__))

from src.agents import payment_agent, delivery_agent

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
INPUT_DIR = os.path.join(os.path.dirname(__file__), "input")
ORDERS_CSV = os.path.join(DATA_DIR, "olist_orders_dataset.csv")
ITEMS_CSV = os.path.join(DATA_DIR, "olist_order_items_dataset.csv")


def load_orders():
    """Load orders CSV, index by order_id."""
    orders = {}
    with open(ORDERS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            oid = row["order_id"].strip().strip('"')
            orders[oid] = row
    return orders


def load_items():
    """Load order_items CSV, group by order_id."""
    items = {}
    with open(ITEMS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            oid = row["order_id"].strip().strip('"')
            items.setdefault(oid, []).append(row)
    return items


def test_case(case_file, orders_db, items_db):
    """Test 1 case với cả 2 agent."""
    with open(case_file, "r", encoding="utf-8") as f:
        case = json.load(f)

    case_id = case["case_id"]
    order_id = case["customer_request"]["claimed_order_id"]
    message = case["customer_request"]["message"]

    print(f"\n{'='*70}")
    print(f"Case: {case_id}")
    print(f"Order: {order_id}")
    print(f"Message: {message[:60]}...")

    # Lấy order
    order = orders_db.get(order_id)
    if not order:
        print(f"  ❌ Order not found in CSV!")
        return

    order_status = order.get("order_status", "").strip().strip('"')
    print(f"  Order Status: {order_status}")

    # Lấy items (có thể rỗng)
    items = items_db.get(order_id, [])
    print(f"  Items count: {len(items)}")

    # Tính item_total và freight_total (giả lập Người 1)
    item_total = round(sum(float(it.get("price", 0)) for it in items), 2)
    freight_total = round(sum(float(it.get("freight_value", 0)) for it in items), 2)
    print(f"  Item total: {item_total} BRL")
    print(f"  Freight total: {freight_total} BRL")

    # --- Payment Agent ---
    pay_result = payment_agent.run(order_id, item_total, freight_total)
    print(f"\n  💳 Payment Agent:")
    print(f"     Payment rows: {pay_result['payment_count']}")
    print(f"     Payment total: {pay_result['payment_total_brl']} BRL")
    print(f"     Valid split payment: {pay_result['has_valid_split_payment']}")
    print(f"     Evidence: {pay_result['evidence_ids'][:3]}...")

    # --- Delivery Agent ---
    del_result = delivery_agent.run(order, items)
    print(f"\n  🚚 Delivery Agent:")
    print(f"     Delivery late: {del_result['delivery_late']}")
    print(f"     Seller late: {del_result['seller_late']}")
    print(f"     Logistics late: {del_result['logistics_late']}")
    print(f"     Within estimate: {del_result['delivery_within_estimate']}")
    print(f"     Violating sellers: {del_result['violating_seller_ids']}")
    print(f"     Timestamps: {del_result['timestamps']}")

    # --- Suy luận primary issue (preview cho Policy Agent) ---
    print(f"\n  ⚖️  Preview primary issue:")
    if order_status == "canceled" and pay_result["payment_total_brl"] > 0:
        print(f"     → canceled_order_paid (refund: {pay_result['payment_total_brl']})")
    elif order_status == "unavailable" and pay_result["payment_total_brl"] > 0:
        print(f"     → unavailable_order_paid (refund: {pay_result['payment_total_brl']})")
    elif del_result["delivery_late"] and del_result["seller_late"]:
        print(f"     → late_delivery_seller (refund freight: {freight_total})")
    elif del_result["delivery_late"] and del_result["logistics_late"]:
        print(f"     → late_delivery_logistics (refund freight: {freight_total})")
    elif pay_result["has_valid_split_payment"]:
        print(f"     → valid_split_payment (refund: 0)")
    else:
        print(f"     → unsupported_late_claim (refund: 0)")

    return {
        "case_id": case_id,
        "order_id": order_id,
        "order_status": order_status,
        "payment": pay_result,
        "delivery": del_result,
    }


def main():
    print("Loading orders CSV...")
    orders_db = load_orders()
    print(f"  Loaded {len(orders_db)} orders")

    print("Loading items CSV...")
    items_db = load_items()
    print(f"  Loaded items for {len(items_db)} orders")

    print("Loading payments CSV (via Payment Agent)...")
    # Trigger cache load
    payment_agent._load_payments()
    print(f"  Payments loaded and cached")

    # Test tất cả 50 cases
    stats = {
        "canceled_order_paid": 0,
        "unavailable_order_paid": 0,
        "late_delivery_seller": 0,
        "late_delivery_logistics": 0,
        "valid_split_payment": 0,
        "unsupported_late_claim": 0,
        "unknown": 0,
    }

    for i in range(1, 51):
        case_file = os.path.join(INPUT_DIR, f"EC_{i:03d}.json")
        if os.path.exists(case_file):
            result = test_case(case_file, orders_db, items_db)
            if result:
                order_status = result["order_status"]
                pay = result["payment"]
                deli = result["delivery"]

                if order_status == "canceled" and pay["payment_total_brl"] > 0:
                    stats["canceled_order_paid"] += 1
                elif order_status == "unavailable" and pay["payment_total_brl"] > 0:
                    stats["unavailable_order_paid"] += 1
                elif deli["delivery_late"] and deli["seller_late"]:
                    stats["late_delivery_seller"] += 1
                elif deli["delivery_late"] and deli["logistics_late"]:
                    stats["late_delivery_logistics"] += 1
                elif pay["has_valid_split_payment"]:
                    stats["valid_split_payment"] += 1
                elif deli["delivery_within_estimate"]:
                    stats["unsupported_late_claim"] += 1
                else:
                    stats["unknown"] += 1

    print(f"\n{'='*70}")
    print("📊 THỐNG KÊ 50 CASES:")
    print(f"{'='*70}")
    for issue, count in stats.items():
        print(f"  {issue:30s}: {count}")
    print(f"  {'TOTAL':30s}: {sum(stats.values())}")


if __name__ == "__main__":
    main()
