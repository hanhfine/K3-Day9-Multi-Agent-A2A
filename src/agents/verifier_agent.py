"""
Verifier Agent — Người 3
==========================
Kiểm tra output JSON do Policy Agent sinh ra, TRƯỚC khi coordinator ghi file vào
output/. Không tự sửa dữ liệu — chỉ báo cáo lỗi để pipeline quyết định.

Kiểm tra:
  1. Schema đủ field bắt buộc theo README mục 6.
  2. Giá trị enum hợp lệ (primary_issue, case_status), confidence trong [0, 1].
  3. Giới hạn số lượng entity/evidence/cause/party/action.
  4. Evidence ID đúng định dạng VÀ thực sự tồn tại trong dữ liệu (chống false positive).
  5. Consistency: case_status / refund / responsible party / action phải khớp policy.
  6. Toàn bộ số tiền đã làm tròn 2 chữ số thập phân.
"""

import re
from typing import Any

from .policy_agent import (
    MAX_ACTIONS,
    MAX_CAUSES,
    MAX_ENTITY,
    MAX_EVIDENCE,
    MAX_PARTIES,
    PRIMARY_ISSUES,
    ROOT_CAUSE_CODES,
)

_EV_PATTERNS = {
    "order": re.compile(r"^order:[^:]+$"),
    "item": re.compile(r"^item:[^:]+:[^:]+$"),
    "payment": re.compile(r"^payment:[^:]+:[^:]+$"),
    "seller": re.compile(r"^seller:[^:]+$"),
    "policy": re.compile(r"^policy:[A-Z_]+$"),
}

# Ánh xạ policy → giá trị bắt buộc, dùng để kiểm tra consistency
ACTION_BY_ISSUE = {
    "canceled_order_paid": "issue_full_refund",
    "unavailable_order_paid": "issue_full_refund",
    "late_delivery_seller": "refund_freight",
    "late_delivery_logistics": "refund_freight",
    "valid_split_payment": "explain_valid_split_payment",
    "unsupported_late_claim": "reject_late_refund",
}

STATUS_BY_ISSUE = {
    "canceled_order_paid": "action_required",
    "unavailable_order_paid": "action_required",
    "late_delivery_seller": "action_required",
    "late_delivery_logistics": "action_required",
    "valid_split_payment": "no_action",
    "unsupported_late_claim": "no_action",
}

# party_type bắt buộc khi có responsible party (None => phải rỗng)
PARTY_TYPE_BY_ISSUE = {
    "canceled_order_paid": "platform",
    "unavailable_order_paid": "platform",
    "late_delivery_seller": "seller",
    "late_delivery_logistics": "logistics_provider",
    "valid_split_payment": None,
    "unsupported_late_claim": None,
}


def _is_rounded_2dp(x: Any) -> bool:
    try:
        return abs(round(float(x), 2) - float(x)) < 1e-9
    except (TypeError, ValueError):
        return False


def _evidence_universe(order_seller: dict[str, Any], payment: dict[str, Any]) -> set[str]:
    """Tập evidence ID hợp lệ dựng được từ dữ liệu thật (Người 1 + Người 2) cộng
    policy:<code> cho mọi root-cause code hợp lệ."""
    universe: set[str] = set(order_seller.get("evidence_ids", []))
    universe.update(payment.get("evidence_ids", []))
    universe.update(f"policy:{code}" for code in ROOT_CAUSE_CODES)
    return universe


def verify(
    output: dict[str, Any],
    order_seller: dict[str, Any],
    payment: dict[str, Any],
    delivery: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Kiểm tra 1 output JSON.

    Args:
        output: dict do policy_agent.evaluate() trả về.
        order_seller, payment, delivery: handoff gốc dùng để đối chiếu evidence.

    Returns:
        (is_valid, errors) — is_valid=True khi errors rỗng.
    """
    errors: list[str] = []

    def require(cond: bool, msg: str) -> None:
        if not cond:
            errors.append(msg)

    # --- 1. Schema đủ field ---
    required_top = (
        "case_id", "assessment", "affected_entities",
        "root_cause_analysis", "evidence_ids", "financial_resolution", "resolution_actions",
    )
    for key in required_top:
        require(key in output, f"Thiếu field bắt buộc: '{key}'")
    if errors:
        return False, errors  # thiếu field gốc thì không kiểm tra sâu hơn được nữa

    assessment = output["assessment"]
    entities = output["affected_entities"]
    rca = output["root_cause_analysis"]
    fin = output["financial_resolution"]
    evidence_ids = output["evidence_ids"]
    actions = output["resolution_actions"]

    for key in ("primary_issue", "case_status", "confidence"):
        require(key in assessment, f"Thiếu assessment.{key}")
    for key in ("order_ids", "item_ids", "seller_ids", "payment_ids"):
        require(key in entities, f"Thiếu affected_entities.{key}")
    for key in ("ranked_causes", "responsible_parties"):
        require(key in rca, f"Thiếu root_cause_analysis.{key}")
    for key in ("currency", "item_total_brl", "freight_total_brl", "payment_total_brl", "recommended_refund_brl"):
        require(key in fin, f"Thiếu financial_resolution.{key}")
    if errors:
        return False, errors

    primary_issue = assessment.get("primary_issue")
    case_status = assessment.get("case_status")
    confidence = assessment.get("confidence")

    # --- 2. Enum + range ---
    require(primary_issue in PRIMARY_ISSUES, f"primary_issue không hợp lệ: {primary_issue!r}")
    require(case_status in ("action_required", "no_action"), f"case_status không hợp lệ: {case_status!r}")
    require(
        isinstance(confidence, (int, float)) and not isinstance(confidence, bool) and 0.0 <= confidence <= 1.0,
        f"confidence ngoài đoạn [0,1]: {confidence!r}",
    )

    # --- 3. Giới hạn số lượng ---
    require(len(entities.get("order_ids", [])) <= MAX_ENTITY, "order_ids vượt quá 5")
    require(len(entities.get("item_ids", [])) <= MAX_ENTITY, "item_ids vượt quá 5")
    require(len(entities.get("seller_ids", [])) <= MAX_ENTITY, "seller_ids vượt quá 5")
    require(len(entities.get("payment_ids", [])) <= MAX_ENTITY, "payment_ids vượt quá 5")
    require(len(evidence_ids) <= MAX_EVIDENCE, "evidence_ids vượt quá 10")
    require(len(rca.get("ranked_causes", [])) <= MAX_CAUSES, "ranked_causes vượt quá 3")
    require(len(rca.get("responsible_parties", [])) <= MAX_PARTIES, "responsible_parties vượt quá 3")
    require(len(actions) <= MAX_ACTIONS, "resolution_actions vượt quá 5")
    require(len(actions) >= 1, "resolution_actions không được rỗng")

    # --- 4. Evidence: định dạng + tồn tại trong dữ liệu (chống false positive) ---
    universe = _evidence_universe(order_seller, payment)
    for ev in evidence_ids:
        prefix = ev.split(":", 1)[0] if ":" in ev else ev
        pattern = _EV_PATTERNS.get(prefix)
        if not pattern or not pattern.match(ev):
            errors.append(f"Evidence sai định dạng: {ev!r}")
            continue
        if ev not in universe:
            errors.append(f"Evidence false positive (không có trong dữ liệu): {ev!r}")

    for rc in rca.get("ranked_causes", []):
        require(
            rc.get("cause_code") in ROOT_CAUSE_CODES,
            f"cause_code không hợp lệ: {rc.get('cause_code')!r}",
        )

    # --- 5. Consistency với policy đã khớp ---
    expected_status = STATUS_BY_ISSUE.get(primary_issue)
    require(
        case_status == expected_status,
        f"case_status={case_status!r} không khớp primary_issue={primary_issue!r} (kỳ vọng {expected_status!r})",
    )

    expected_action = ACTION_BY_ISSUE.get(primary_issue)
    require(
        expected_action is None or expected_action in actions,
        f"resolution_actions thiếu action kỳ vọng {expected_action!r} cho primary_issue={primary_issue!r}",
    )

    refund = fin.get("recommended_refund_brl")
    if isinstance(refund, (int, float)):
        if primary_issue in ("canceled_order_paid", "unavailable_order_paid"):
            require(
                abs(refund - fin.get("payment_total_brl", 0.0)) < 0.01,
                "recommended_refund_brl phải bằng payment_total_brl",
            )
        elif primary_issue in ("late_delivery_seller", "late_delivery_logistics"):
            require(
                abs(refund - fin.get("freight_total_brl", 0.0)) < 0.01,
                "recommended_refund_brl phải bằng freight_total_brl",
            )
        elif primary_issue in ("valid_split_payment", "unsupported_late_claim"):
            require(abs(refund - 0.0) < 0.01, "recommended_refund_brl phải bằng 0.0")
    else:
        errors.append("recommended_refund_brl không phải số")

    expected_party_type = PARTY_TYPE_BY_ISSUE.get(primary_issue)
    parties = rca.get("responsible_parties", [])
    if expected_party_type is None:
        require(len(parties) == 0, f"responsible_parties phải rỗng cho primary_issue={primary_issue!r}")
    else:
        require(len(parties) >= 1, f"responsible_parties không được rỗng cho primary_issue={primary_issue!r}")
        require(
            all(p.get("party_type") == expected_party_type for p in parties),
            f"responsible_parties.party_type phải là {expected_party_type!r}",
        )

    # --- 6. Làm tròn 2 chữ số thập phân ---
    for field in ("item_total_brl", "freight_total_brl", "payment_total_brl", "recommended_refund_brl"):
        val = fin.get(field)
        require(_is_rounded_2dp(val), f"financial_resolution.{field} chưa làm tròn 2 chữ số thập phân: {val!r}")

    require(fin.get("currency") == "BRL", f"currency phải là 'BRL', nhận {fin.get('currency')!r}")

    return len(errors) == 0, errors
