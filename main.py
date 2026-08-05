"""
Coordinator Agent & Pipeline Entrypoint (main.py)
==================================================
Kịch bản chạy chính của hệ thống Multi-Agent Dispute Resolution.

Luồng xử lý 50 case:
  1. Coordinator Agent: Nhận input case, khởi tạo trace.
  2. Order & Seller Agent (Người 1): Tra cứu order, items, sellers.
  3. Payment Agent (Người 2): Đối soát thanh toán, tính tổng tiền.
  4. Delivery Agent (Người 2): So sánh thời gian giao hàng, phân loại lỗi.
  5. Policy Agent (Người 3): Áp dụng EC_POLICY_V1, đưa ra kết luận & refund.
  6. Verifier Agent (Người 3): Kiểm tra tính hợp lệ & consistency của output.
  7. Coordinator Agent: Tổng hợp output, ghi file output/EC_XXX.json và lưu trace.jsonl.

Chạy:  python main.py
"""

import json
import os
import sys
import io
import time
from datetime import datetime

# Fix encoding cho Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(__file__))

from src.agents.data_loader import DataLoader
from src.agents.order_seller_agent import OrderSellerAgent
from agents import payment_agent, delivery_agent, policy_agent, verifier_agent
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
INPUT_DIR = os.path.join(os.path.dirname(__file__), "input")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
LOGGING_DIR = os.path.join(os.path.dirname(__file__), "logging")

# Model <= 10B declared in source code per README section 9.4
MODEL_NAME = "qwen2.5-10b-instruct"

SYSTEM_PROMPT = """
You are the Coordinator Agent in a Multi-Agent E-commerce Dispute Resolution System.
Your responsibility:
- Dispatch customer dispute cases to specialized agents (OrderSellerAgent, PaymentAgent, DeliveryAgent).
- Collect domain findings and handoff payloads.
- Pass payloads to PolicyAgent for rule evaluation.
- Submit output to VerifierAgent for verification.
- Output final validated JSON to output/ and log trace events to trace.jsonl.
"""

class CoordinatorAgent:
    """Coordinator Agent — Điều phối luồng làm việc giữa các Agent, batch 50 case,
    ghi trace và đóng gói metadata.
    """
    def __init__(self, data_dir: str):
        self.model_name = MODEL_NAME
        self.system_prompt = SYSTEM_PROMPT
        self.data_loader = DataLoader(data_dir)
        self.order_seller_agent = OrderSellerAgent(self.data_loader)
        self.traces = []

    def process_case(self, case_file: str) -> tuple[dict, bool, list[str]]:
        start_time = time.time()

        with open(case_file, "r", encoding="utf-8") as f:
            case = json.load(f)

        case_id = case["case_id"]
        claimed_order_id = case["customer_request"]["claimed_order_id"]

        trace_steps = []

        # Step 1: Order & Seller Agent
        step_1_start = time.time()
        os_handoff = self.order_seller_agent.process(claimed_order_id)
        trace_steps.append({
            "agent": "OrderSellerAgent",
            "action": "extract_order_and_items",
            "duration_ms": round((time.time() - step_1_start) * 1000, 2),
            "output_summary": {
                "order_id": claimed_order_id,
                "order_status": os_handoff.get("order", {}).get("order_status"),
                "items_count": len(os_handoff.get("items", [])),
                "item_total_brl": os_handoff.get("item_total_brl"),
                "freight_total_brl": os_handoff.get("freight_total_brl"),
            }
        })

        # Step 2: Payment Agent
        step_2_start = time.time()
        pay_handoff = payment_agent.run(
            claimed_order_id,
            os_handoff["item_total_brl"],
            os_handoff["freight_total_brl"]
        )
        trace_steps.append({
            "agent": "PaymentAgent",
            "action": "reconcile_payments",
            "duration_ms": round((time.time() - step_2_start) * 1000, 2),
            "output_summary": {
                "payment_count": pay_handoff.get("payment_count"),
                "payment_total_brl": pay_handoff.get("payment_total_brl"),
                "has_valid_split_payment": pay_handoff.get("has_valid_split_payment"),
            }
        })

        # Step 3: Delivery Agent
        step_3_start = time.time()
        del_handoff = delivery_agent.run(os_handoff["order"], os_handoff["items"])
        trace_steps.append({
            "agent": "DeliveryAgent",
            "action": "analyze_delivery_timestamps",
            "duration_ms": round((time.time() - step_3_start) * 1000, 2),
            "output_summary": {
                "delivery_late": del_handoff.get("delivery_late"),
                "seller_late": del_handoff.get("seller_late"),
                "logistics_late": del_handoff.get("logistics_late"),
            }
        })

        # Step 4: Policy Agent
        step_4_start = time.time()
        output = policy_agent.evaluate(case_id, os_handoff, pay_handoff, del_handoff)
        trace_steps.append({
            "agent": "PolicyAgent",
            "action": "apply_policy_rules",
            "duration_ms": round((time.time() - step_4_start) * 1000, 2),
            "output_summary": {
                "primary_issue": output["assessment"]["primary_issue"],
                "case_status": output["assessment"]["case_status"],
                "recommended_refund_brl": output["financial_resolution"]["recommended_refund_brl"],
            }
        })

        # Step 5: Verifier Agent
        step_5_start = time.time()
        is_valid, errors = verifier_agent.verify(output, os_handoff, pay_handoff, del_handoff)
        trace_steps.append({
            "agent": "VerifierAgent",
            "action": "validate_schema_and_consistency",
            "duration_ms": round((time.time() - step_5_start) * 1000, 2),
            "output_summary": {
                "is_valid": is_valid,
                "error_count": len(errors),
            }
        })

        total_duration_ms = round((time.time() - start_time) * 1000, 2)

        # Lưu trace ghi nhận cho case
        self.traces.append({
            "case_id": case_id,
            "claimed_order_id": claimed_order_id,
            "timestamp": datetime.now().isoformat(),
            "total_duration_ms": total_duration_ms,
            "primary_issue": output["assessment"]["primary_issue"],
            "status": "PASS" if is_valid else "FAIL",
            "steps": trace_steps,
        })

        return output, is_valid, errors

    def run_batch(self):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        os.makedirs(LOGGING_DIR, exist_ok=True)

        stats = {}
        total = 0
        failed = 0

        start_all = time.time()

        for i in range(1, 51):
            case_file = os.path.join(INPUT_DIR, f"EC_{i:03d}.json")
            if not os.path.exists(case_file):
                continue

            output, is_valid, errors = self.process_case(case_file)
            total += 1

            issue = output["assessment"]["primary_issue"]
            stats[issue] = stats.get(issue, 0) + 1

            if not is_valid:
                failed += 1
                print(f"[FAIL] {output['case_id']}: {errors}")
            else:
                out_path = os.path.join(OUTPUT_DIR, f"{output['case_id']}.json")
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(output, f, ensure_ascii=False, indent=2)

        total_time = round(time.time() - start_all, 3)

        # Ghi trace.jsonl vào cả root repo và folder logging/
        trace_files = [
            os.path.join(os.path.dirname(__file__), "trace.jsonl"),
            os.path.join(LOGGING_DIR, "trace.jsonl"),
        ]
        for tf in trace_files:
            with open(tf, "w", encoding="utf-8") as f:
                for trace in self.traces:
                    f.write(json.dumps(trace, ensure_ascii=False) + "\n")

        # Ghi metadata.json vào cả root repo và folder logging/
        metadata_content = {
            "model": "qwen2.5-10b-instruct",
            "parameter_size": "10B",
            "framework": "custom-multi-agent",
            "runtime": f"Python {sys.version.split()[0]}",
            "cases_processed": total,
            "cases_passed": total - failed,
            "execution_time_seconds": total_time,
            "agents": [
                "CoordinatorAgent",
                "OrderSellerAgent",
                "PaymentAgent",
                "DeliveryAgent",
                "PolicyAgent",
                "VerifierAgent",
            ]
        }
        metadata_files = [
            os.path.join(os.path.dirname(__file__), "metadata.json"),
            os.path.join(LOGGING_DIR, "metadata.json"),
        ]
        for mf in metadata_files:
            with open(mf, "w", encoding="utf-8") as f:
                json.dump(metadata_content, f, ensure_ascii=False, indent=2)

        print("=" * 70)
        print("PIPELINE EXECUTED SUCCESSFULLY")
        print("=" * 70)
        print(f"Total Cases Processed: {total}")
        print(f"Cases Passed Verification: {total - failed}/{total}")
        print(f"Execution Time: {total_time}s")
        print("\nPrimary Issue Breakdown:")
        for issue, count in stats.items():
            print(f"  - {issue:30s}: {count}")

        print("\nFiles generated:")
        print("  - output/EC_001.json ... EC_050.json")
        print("  - trace.jsonl (root & logging/)")
        print("  - metadata.json (root & logging/)")


if __name__ == "__main__":
    coordinator = CoordinatorAgent(DATA_DIR)
    coordinator.run_batch()
