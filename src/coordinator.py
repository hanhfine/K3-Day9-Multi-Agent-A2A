"""
Coordinator — Người 4 (Coordinator, Integration & Documentation).

Điều phối pipeline cho MỖI case theo đúng thứ tự:

    load case
      -> Order/Seller Agent      (Người 1: src/agents/order_seller_agent.py)
      -> Payment Agent           (Người 2: agents/payment_agent.py)
      -> Delivery Agent          (Người 2: agents/delivery_agent.py)
      -> Policy Agent            (Người 3: agents/policy_agent.py)
      -> Verifier Agent          (Người 3: agents/verifier_agent.py)
      -> Coordinator Reasoning   (Người 4: LLM Groq — chỉ giải thích, không
                                  ghi đè số liệu đã được verify)

Mỗi bước sinh 1 hoặc nhiều trace event riêng biệt, ghi ra logging/trace.jsonl.
Coordinator KHÔNG tự tính lại số liệu nghiệp vụ — mọi con số/boolean quyết
định luôn đến từ agent tương ứng, giữ đúng nguyên tắc "không suy diễn sự kiện
ngoài dữ liệu CSV" trong README.md.

LLM reasoning pass dùng Groq (llama-3.1-8b-instant, ~8B tham số, tuân thủ giới
hạn <=10B của đề bài) để sinh phần diễn giải bằng tiếng Việt cho khách hàng và
tự đối chiếu tính nhất quán (sanity check) — hoàn toàn tách biệt khỏi engine
quyết định deterministic của Người 1/2/3, nên không ảnh hưởng độ chính xác của
output đã được Verifier Agent xác nhận.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from agents import delivery_agent, payment_agent, policy_agent, verifier_agent  # Người 2, 3
from src.agents.data_loader import DataLoader  # Người 1
from src.agents.order_seller_agent import OrderSellerAgent  # Người 1
from src.llm_client import LLMError, call_agent_llm

COORDINATOR_SYSTEM_PROMPT = (
    "Bạn là Coordinator Reasoning Agent trong hệ thống multi-agent xử lý khiếu nại "
    "thương mại điện tử Olist. Bạn nhận nội dung khiếu nại của khách và kết luận "
    "CUỐI CÙNG đã được Policy Agent + Verifier Agent xác định (deterministic, đã "
    "kiểm chứng với dữ liệu CSV thật, không thể thay đổi). Nhiệm vụ của bạn CHỈ có "
    "hai việc: (1) viết một đoạn tóm tắt ngắn gọn bằng tiếng Việt giải thích cho "
    "khách hàng vì sao có kết luận này, dựa DUY NHẤT trên các trường dữ liệu được "
    "cung cấp; (2) tự đối chiếu xem kết luận có nhất quán logic với dữ liệu hay "
    "không (sanity check). TUYỆT ĐỐI không tự bịa thêm sự kiện ngoài input, không "
    "đề xuất thay đổi số liệu. Trả lời đúng JSON schema: "
    '{"summary_vi": string, "sanity_check_pass": bool, "sanity_notes": string}'
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Coordinator:
    """Nạp dữ liệu 1 lần, chạy pipeline cho từng case trong batch 50."""

    def __init__(self, data_dir: str, use_llm: bool = True):
        self.loader = DataLoader(data_dir)
        self.order_seller_agent = OrderSellerAgent(self.loader)
        self.use_llm = use_llm

    def _coordinator_reasoning(self, case: dict, output: dict) -> tuple[dict | None, str | None]:
        if not self.use_llm:
            return None, "llm_disabled"
        user_payload = {
            "customer_message": case["customer_request"]["message"],
            "final_assessment": output["assessment"],
            "financial_resolution": output["financial_resolution"],
            "root_cause_analysis": output["root_cause_analysis"],
            "resolution_actions": output["resolution_actions"],
        }
        try:
            result = call_agent_llm(
                COORDINATOR_SYSTEM_PROMPT, json.dumps(user_payload, ensure_ascii=False)
            )
            return result, None
        except LLMError as exc:
            return None, str(exc)

    def run_case(self, case_path: str) -> dict:
        """Chạy 1 case qua toàn bộ chuỗi agent. Trả về output + trace events."""
        with open(case_path, "r", encoding="utf-8") as f:
            case = json.load(f)

        case_id = case["case_id"]
        order_id = case["customer_request"]["claimed_order_id"]
        trace_events: list[dict] = []

        def log(agent: str, event: str, payload: dict) -> None:
            trace_events.append(
                {
                    "ts": _now_iso(),
                    "case_id": case_id,
                    "agent": agent,
                    "event": event,
                    "payload": payload,
                }
            )

        log(
            "coordinator",
            "case_loaded",
            {"order_id": order_id, "policy_version": case.get("policy_version")},
        )

        # --- Người 1: Order/Seller Agent ---
        os_handoff = self.order_seller_agent.process(order_id)
        log(
            "order_seller_agent",
            "handoff",
            {
                "seller_handoff_late": os_handoff.get("seller_handoff_late"),
                "violating_seller_ids": os_handoff.get("violating_seller_ids"),
                "item_total_brl": os_handoff.get("item_total_brl"),
                "freight_total_brl": os_handoff.get("freight_total_brl"),
                "evidence_ids": os_handoff.get("evidence_ids"),
            },
        )

        # --- Người 2: Payment Agent ---
        pay_handoff = payment_agent.run(
            order_id, os_handoff["item_total_brl"], os_handoff["freight_total_brl"]
        )
        log(
            "payment_agent",
            "handoff",
            {
                "payment_total_brl": pay_handoff.get("payment_total_brl"),
                "has_valid_split_payment": pay_handoff.get("has_valid_split_payment"),
                "evidence_ids": pay_handoff.get("evidence_ids"),
            },
        )

        # --- Người 2: Delivery Agent ---
        del_handoff = delivery_agent.run(os_handoff["order"], os_handoff["items"])
        log(
            "delivery_agent",
            "handoff",
            {
                "delivery_late": del_handoff.get("delivery_late"),
                "seller_late": del_handoff.get("seller_late"),
                "logistics_late": del_handoff.get("logistics_late"),
                "delivery_within_estimate": del_handoff.get("delivery_within_estimate"),
            },
        )

        # --- Người 3: Policy Agent ---
        output = policy_agent.evaluate(case_id, os_handoff, pay_handoff, del_handoff)
        log(
            "policy_agent",
            "decision",
            {
                "primary_issue": output["assessment"]["primary_issue"],
                "case_status": output["assessment"]["case_status"],
                "confidence": output["assessment"]["confidence"],
                "recommended_refund_brl": output["financial_resolution"]["recommended_refund_brl"],
            },
        )

        # --- Người 3: Verifier Agent ---
        is_valid, errors = verifier_agent.verify(output, os_handoff, pay_handoff, del_handoff)
        log("verifier_agent", "verification", {"is_valid": is_valid, "errors": errors})

        # --- Người 4: Coordinator LLM reasoning (bổ sung, không ghi đè số liệu) ---
        llm_output, llm_error = self._coordinator_reasoning(case, output)
        log(
            "coordinator_llm",
            "reasoning",
            {"model": "llama-3.1-8b-instant", "output": llm_output, "error": llm_error},
        )

        return {
            "case_id": case_id,
            "order_id": order_id,
            "output": output,
            "is_valid": is_valid,
            "errors": errors,
            "trace_events": trace_events,
        }
