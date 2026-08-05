import pandas as pd
from typing import Dict, Any

# Model <= 10B declared in source code per README section 9.4
MODEL_NAME = "qwen2.5-10b-instruct"

SYSTEM_PROMPT = """
You are the Order & Seller Agent in a Multi-Agent E-commerce Dispute Resolution System.
Your responsibility:
- Analyze order status, item details, seller information, and freight costs.
- Compare order_delivered_carrier_date with shipping_limit_date for each item.
- Identify if seller handed off items after shipping_limit_date.
- Extract structured evidence: order:<order_id>, item:<order_id>:<item_id>, seller:<seller_id>.
"""

class OrderSellerAgent:
    def __init__(self, data_loader):
        self.data_loader = data_loader
        self.model_name = MODEL_NAME
        self.system_prompt = SYSTEM_PROMPT

    def process(self, claimed_order_id: str) -> Dict[str, Any]:
        data = self.data_loader.get_order_data(claimed_order_id)
        
        if not data:
            # Trả về kết quả rỗng nếu không tìm thấy order
            return {
                "order": {},
                "items": [],
                "seller_handoff_late": False,
                "violating_seller_ids": [],
                "item_total_brl": 0.0,
                "freight_total_brl": 0.0,
                "evidence_ids": []
            }
            
        order = data["order"]
        items = data["items"]
        
        seller_handoff_late = False
        violating_seller_ids = set()
        item_total_brl = 0.0
        freight_total_brl = 0.0
        evidence_ids = []
        
        # Evidence: order
        evidence_ids.append(f"order:{claimed_order_id}")
        
        carrier_date = order.get("order_delivered_carrier_date")
        is_carrier_date_valid = pd.notna(carrier_date)
        
        for item in items:
            item_id = item["order_item_id"]
            seller_id = item["seller_id"]
            price = float(item["price"])
            freight = float(item["freight_value"])
            limit_date = item["shipping_limit_date"]
            
            item_total_brl += price
            freight_total_brl += freight
            
            # Logic for seller_handoff_late
            if is_carrier_date_valid and pd.notna(limit_date):
                if carrier_date > limit_date:
                    seller_handoff_late = True
                    violating_seller_ids.add(seller_id)
            
        # Thu thập item evidence
        item_evidences = [f"item:{claimed_order_id}:{item['order_item_id']}" for item in items]
        
        # Thu thập seller evidence (chỉ lấy những seller unique để tránh lặp)
        seller_evidences = []
        for item in items:
            ev_str = f"seller:{item['seller_id']}"
            if ev_str not in seller_evidences:
                seller_evidences.append(ev_str)
        
        # Yêu cầu của người 1: Giới hạn tối đa 5 item_ids và 5 seller_ids cho evidence
        evidence_ids.extend(item_evidences[:5])
        evidence_ids.extend(seller_evidences[:5])
        
        # Format timestamps an toàn cho JSON (chuyển Timestamp -> chuỗi, NaT -> None)
        safe_order = {}
        for k, v in order.items():
            if pd.isna(v):
                safe_order[k] = None
            elif isinstance(v, pd.Timestamp):
                safe_order[k] = v.isoformat()
            else:
                safe_order[k] = v
                
        safe_items = []
        for item in items:
            safe_item = {}
            for k, v in item.items():
                if pd.isna(v):
                    safe_item[k] = None
                elif isinstance(v, pd.Timestamp):
                    safe_item[k] = v.isoformat()
                else:
                    safe_item[k] = v
            safe_items.append(safe_item)

        return {
            "order": safe_order,
            "items": safe_items,
            "seller_handoff_late": seller_handoff_late,
            "violating_seller_ids": list(violating_seller_ids),
            "item_total_brl": round(item_total_brl, 2),
            "freight_total_brl": round(freight_total_brl, 2),
            "evidence_ids": evidence_ids
        }
