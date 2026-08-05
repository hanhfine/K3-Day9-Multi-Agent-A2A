"""
Test script cho Policy Agent và Verifier Agent (Người 3)
===========================================================
Nối pipeline Người 1 (Order/Seller Agent) -> Người 2 (Payment/Delivery Agent)
-> Người 3 (Policy Agent -> Verifier Agent) và chạy trên toàn bộ 50 case input.

Kiểm tra:
  - Đủ 6 loại primary_issue xuất hiện trong 50 case.
  - Verifier Agent không phát hiện lỗi nào (schema, giới hạn, evidence, consistency).
  - Output hợp lệ được ghi vào output/EC_XXX.json.

Chạy:  python test_person3.py
"""

import json
import os
import sys
import io

# Fix Windows console encoding for Vietnamese
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(__file__))

from src.agents.data_loader import DataLoader
from src.agents.order_seller_agent import OrderSellerAgent
from agents import payment_agent, delivery_agent, policy_agent, verifier_agent

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
INPUT_DIR = os.path.join(os.path.dirname(__file__), "input")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def run_case(case_file: str, order_seller_agent: OrderSellerAgent):
    """Chạy 1 case qua toàn bộ chuỗi agent: Người1 -> Người2 -> Người3."""
    with open(case_file, "r", encoding="utf-8") as f:
        case = json.load(f)

    case_id = case["case_id"]
    order_id = case["customer_request"]["claimed_order_id"]

    # --- Người 1: Order/Seller Agent ---
    os_handoff = order_seller_agent.process(order_id)

    # --- Người 2: Payment Agent + Delivery Agent ---
    pay_handoff = payment_agent.run(
        order_id, os_handoff["item_total_brl"], os_handoff["freight_total_brl"]
    )
    del_handoff = delivery_agent.run(os_handoff["order"], os_handoff["items"])

    # --- Người 3: Policy Agent ---
    output = policy_agent.evaluate(case_id, os_handoff, pay_handoff, del_handoff)

    # --- Người 3: Verifier Agent ---
    is_valid, errors = verifier_agent.verify(output, os_handoff, pay_handoff, del_handoff)

    return case_id, output, is_valid, errors


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    loader = DataLoader(DATA_DIR)
    order_seller_agent = OrderSellerAgent(loader)

    stats = {issue: 0 for issue in policy_agent.PRIMARY_ISSUES}
    total = 0
    total_errors = 0
    low_confidence = []
    failed_cases = []

    for i in range(1, 51):
        case_file = os.path.join(INPUT_DIR, f"EC_{i:03d}.json")
        if not os.path.exists(case_file):
            continue

        case_id, output, is_valid, errors = run_case(case_file, order_seller_agent)
        total += 1

        primary_issue = output["assessment"]["primary_issue"]
        stats[primary_issue] += 1

        if output["assessment"]["confidence"] < 0.6:
            low_confidence.append(case_id)

        if not is_valid:
            total_errors += len(errors)
            failed_cases.append((case_id, errors))
            print(f"[FAIL] {case_id}: {len(errors)} lỗi verify")
            for e in errors:
                print(f"     - {e}")
        else:
            out_path = os.path.join(OUTPUT_DIR, f"{case_id}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 70}")
    print("THỐNG KÊ 50 CASES (Policy Agent):")
    print(f"{'=' * 70}")
    for issue, count in stats.items():
        print(f"  {issue:30s}: {count}")
    print(f"  {'TOTAL':30s}: {total}")

    print(f"\nVerifier Agent: {total - len(failed_cases)}/{total} case hợp lệ, {total_errors} lỗi tổng cộng")
    if low_confidence:
        print(f"CẢNH BÁO case confidence < 0.6: {low_confidence}")

    missing_issues = [issue for issue, count in stats.items() if count == 0]
    print(f"\nĐủ 6 loại primary_issue: {'CÓ' if not missing_issues else 'THIẾU ' + str(missing_issues)}")
    print(f"Verifier PASS toàn bộ: {'CÓ' if not failed_cases else 'KHÔNG (' + str(len(failed_cases)) + ' case lỗi)'}")

    assert not missing_issues, f"Thiếu primary_issue: {missing_issues}"
    assert not failed_cases, f"Verifier phát hiện lỗi ở {len(failed_cases)} case"

    print(f"\nTất cả {total} case đã qua Policy Agent + Verifier Agent và được ghi vào output/")


if __name__ == "__main__":
    main()
