"""
Policy Agent — Người 3
========================
Nhận handoff từ:
  - Order/Seller Agent (Người 1)
  - Payment Agent (Người 2)
  - Delivery Agent (Người 2)

Áp dụng EC_POLICY_V1 theo đúng thứ tự ưu tiên (README mục 4) và sinh output JSON cuối
cùng theo schema README mục 6.
"""

from typing import Any

# Model <= 10B declared in source code per README section 9.4
MODEL_NAME = "qwen2.5-10b-instruct"

SYSTEM_PROMPT = """
You are the Policy Agent in a Multi-Agent E-commerce Dispute Resolution System.
Your responsibility:
- Synthesize handoff evidence from OrderSellerAgent, PaymentAgent, and DeliveryAgent.
- Apply EC_POLICY_V1 business rules strictly in priority order:
  1. canceled_order_paid (order_status == 'canceled' and payment > 0)
  2. unavailable_order_paid (order_status == 'unavailable' and payment > 0)
  3. late_delivery_seller (delivered_customer > estimated_delivery and carrier_date > shipping_limit)
  4. late_delivery_logistics (delivered_customer > estimated_delivery and carrier_date <= shipping_limit)
  5. valid_split_payment (payment_count >= 2 and abs(payment_total - (item_total + freight_total)) <= 0.10)
  6. unsupported_late_claim (delivered_customer <= estimated_delivery and payment matches)
- Output full financial resolution (item_total_brl, freight_total_brl, payment_total_brl, recommended_refund_brl).
- Specify resolution actions and affected entity IDs within constraints.
"""


# Root-cause code hợp lệ (README mục 4)
ROOT_CAUSE_CODES = {
    "SELLER_HANDOFF_AFTER_LIMIT",
    "CARRIER_DELIVERED_AFTER_ESTIMATE",
    "ORDER_CANCELED_AFTER_PAYMENT",
    "ORDER_UNAVAILABLE_AFTER_PAYMENT",
    "MULTIPLE_PAYMENTS_RECONCILED",
    "DELIVERY_WITHIN_ESTIMATE",
}

# primary_issue hợp lệ, đúng thứ tự ưu tiên áp dụng rule
PRIMARY_ISSUES = (
    "canceled_order_paid",
    "unavailable_order_paid",
    "late_delivery_seller",
    "late_delivery_logistics",
    "valid_split_payment",
    "unsupported_late_claim",
)

# Giới hạn theo README mục 6
MAX_ENTITY = 5
MAX_EVIDENCE = 10
MAX_CAUSES = 3
MAX_PARTIES = 3
MAX_ACTIONS = 5


def _r2(x: Any) -> float:
    """Làm tròn 2 chữ số thập phân, tránh -0.0."""
    v = round(float(x or 0.0), 2)
    return 0.0 if v == 0 else v


def _by_prefix(evidence_ids: list[str], prefix: str) -> list[str]:
    return [e for e in evidence_ids if e.startswith(prefix)]


def _build_evidence(order_ev: list[str], extra_groups: list[list[str]], cause_code: str) -> list[str]:
    """Ghép order evidence + các nhóm evidence liên quan trực tiếp đến rule đã khớp,
    rồi thêm policy:<cause_code>. Luôn giữ tổng <= MAX_EVIDENCE (10).

    Không gộp bừa mọi evidence Người 1/2 đưa lên — chỉ lấy evidence thật sự hỗ trợ
    cho root cause đã chọn, tránh false positive.
    """
    ev: list[str] = list(order_ev)
    for group in extra_groups:
        ev.extend(group)
    # dedupe, giữ thứ tự
    seen = set()
    deduped = []
    for e in ev:
        if e not in seen:
            seen.add(e)
            deduped.append(e)
    deduped = deduped[: MAX_EVIDENCE - 1]  # chừa 1 chỗ cho policy code
    deduped.append(f"policy:{cause_code}")
    return deduped


def evaluate(
    case_id: str,
    order_seller: dict[str, Any],
    payment: dict[str, Any],
    delivery: dict[str, Any],
) -> dict[str, Any]:
    """Áp dụng EC_POLICY_V1 theo thứ tự ưu tiên, trả về output JSON đúng schema README.

    Args:
        case_id: mã case, vd "EC_001".
        order_seller: handoff từ OrderSellerAgent.process() (Người 1).
        payment: handoff từ payment_agent.run() (Người 2).
        delivery: handoff từ delivery_agent.run() (Người 2).

    Returns:
        dict đúng output schema (README mục 6), sẵn sàng ghi ra output/<case_id>.json
        sau khi qua Verifier Agent.
    """
    order = order_seller.get("order") or {}
    items = order_seller.get("items") or []
    order_id = order.get("order_id") or ""
    order_status = str(order.get("order_status") or "").strip().strip('"')

    item_total = _r2(order_seller.get("item_total_brl"))
    freight_total = _r2(order_seller.get("freight_total_brl"))
    payment_total = _r2(payment.get("payment_total_brl"))

    order_ev = _by_prefix(order_seller.get("evidence_ids", []), "order:")
    item_ev = _by_prefix(order_seller.get("evidence_ids", []), "item:")
    seller_ev = _by_prefix(order_seller.get("evidence_ids", []), "seller:")
    payment_ev = list(payment.get("evidence_ids", []))[:MAX_ENTITY]

    violating_sellers = list(
        order_seller.get("violating_seller_ids") or delivery.get("violating_seller_ids") or []
    )[:MAX_ENTITY]
    seller_ev_violating = [e for e in seller_ev if e.split(":", 1)[-1] in violating_sellers] or seller_ev

    # affected_entities phản ánh dữ liệu thật của order (không lọc theo lỗi/không lỗi)
    all_seller_ids: list[str] = []
    for it in items:
        sid = it.get("seller_id")
        if sid and sid not in all_seller_ids:
            all_seller_ids.append(sid)

    affected_entities = {
        "order_ids": [order_id] if order_id else [],
        "item_ids": [f"{order_id}:{it.get('order_item_id')}" for it in items][:MAX_ENTITY],
        "seller_ids": all_seller_ids[:MAX_ENTITY],
        "payment_ids": list(payment.get("payment_ids", []))[:MAX_ENTITY],
    }

    def _finish(
        primary_issue: str,
        case_status: str,
        confidence: float,
        cause_code: str,
        parties: list[dict[str, str]],
        refund: float,
        action: str,
        evidence_ids: list[str],
    ) -> dict[str, Any]:
        return {
            "case_id": case_id,
            "assessment": {
                "primary_issue": primary_issue,
                "case_status": case_status,
                "confidence": round(min(max(confidence, 0.0), 1.0), 2),
            },
            "affected_entities": affected_entities,
            "root_cause_analysis": {
                "ranked_causes": [{"cause_code": cause_code, "rank": 1}],
                "responsible_parties": parties[:MAX_PARTIES],
            },
            "evidence_ids": evidence_ids[:MAX_EVIDENCE],
            "financial_resolution": {
                "currency": "BRL",
                "item_total_brl": item_total,
                "freight_total_brl": freight_total,
                "payment_total_brl": payment_total,
                "recommended_refund_brl": _r2(refund),
            },
            "resolution_actions": [action][:MAX_ACTIONS],
        }

    # Rule 1: canceled_order_paid
    if order_status == "canceled" and payment_total > 0:
        ev = _build_evidence(order_ev, [item_ev, payment_ev], "ORDER_CANCELED_AFTER_PAYMENT")
        return _finish(
            "canceled_order_paid", "action_required", 0.98,
            "ORDER_CANCELED_AFTER_PAYMENT",
            [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}],
            payment_total, "issue_full_refund", ev,
        )

    # Rule 2: unavailable_order_paid
    if order_status == "unavailable" and payment_total > 0:
        ev = _build_evidence(order_ev, [item_ev, payment_ev], "ORDER_UNAVAILABLE_AFTER_PAYMENT")
        return _finish(
            "unavailable_order_paid", "action_required", 0.98,
            "ORDER_UNAVAILABLE_AFTER_PAYMENT",
            [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}],
            payment_total, "issue_full_refund", ev,
        )

    # Rule 3: late_delivery_seller — giao trễ estimated VÀ carrier nhận hàng sau shipping_limit
    if delivery.get("delivery_late") and delivery.get("seller_late"):
        ev = _build_evidence(order_ev, [item_ev, payment_ev, seller_ev_violating], "SELLER_HANDOFF_AFTER_LIMIT")
        seller_ids_for_parties = violating_sellers or all_seller_ids[:1]
        parties = [{"party_type": "seller", "party_id": sid} for sid in seller_ids_for_parties]
        return _finish(
            "late_delivery_seller", "action_required", 0.95,
            "SELLER_HANDOFF_AFTER_LIMIT", parties,
            freight_total, "refund_freight", ev,
        )

    # Rule 4: late_delivery_logistics — giao trễ estimated NHƯNG seller bàn giao đúng hạn
    if delivery.get("delivery_late") and delivery.get("logistics_late"):
        ev = _build_evidence(order_ev, [item_ev, payment_ev], "CARRIER_DELIVERED_AFTER_ESTIMATE")
        return _finish(
            "late_delivery_logistics", "action_required", 0.95,
            "CARRIER_DELIVERED_AFTER_ESTIMATE",
            [{"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}],
            freight_total, "refund_freight", ev,
        )

    # Rule 5: valid_split_payment — >=2 payment rows, tổng khớp item+freight trong 0.10 BRL
    if payment.get("has_valid_split_payment"):
        ev = _build_evidence(order_ev, [item_ev, payment_ev], "MULTIPLE_PAYMENTS_RECONCILED")
        return _finish(
            "valid_split_payment", "no_action", 0.98,
            "MULTIPLE_PAYMENTS_RECONCILED", [],
            0.0, "explain_valid_split_payment", ev,
        )

    # Rule 6: unsupported_late_claim — fallback mặc định (giao đúng hạn / không đủ cơ sở)
    confidence = 0.95 if delivery.get("delivery_within_estimate") else 0.50
    ev = _build_evidence(order_ev, [item_ev, payment_ev], "DELIVERY_WITHIN_ESTIMATE")
    return _finish(
        "unsupported_late_claim", "no_action", confidence,
        "DELIVERY_WITHIN_ESTIMATE", [],
        0.0, "reject_late_refund", ev,
    )
