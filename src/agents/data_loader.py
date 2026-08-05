import pandas as pd
import os

class DataLoader:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        
        print("Loading CSV files into memory...")
        # Load orders
        self.orders = pd.read_csv(os.path.join(data_dir, "olist_orders_dataset.csv"))
        # Load order items
        self.order_items = pd.read_csv(os.path.join(data_dir, "olist_order_items_dataset.csv"))
        # Load sellers
        self.sellers = pd.read_csv(os.path.join(data_dir, "olist_sellers_dataset.csv"))
        # Load customers
        self.customers = pd.read_csv(os.path.join(data_dir, "olist_customers_dataset.csv"))
        
        # Convert timestamp columns to datetime safely
        timestamp_cols = [
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date"
        ]
        for col in timestamp_cols:
            self.orders[col] = pd.to_datetime(self.orders[col], errors='coerce')
            
        self.order_items["shipping_limit_date"] = pd.to_datetime(self.order_items["shipping_limit_date"], errors='coerce')
        print("Data loading complete.")
        
    def get_order_data(self, order_id: str):
        """Returns order info, items, customer info, and sellers info for a specific order_id."""
        order = self.orders[self.orders["order_id"] == order_id]
        if order.empty:
            return None
            
        items = self.order_items[self.order_items["order_id"] == order_id]
        
        customer_id = order.iloc[0]["customer_id"]
        customer = self.customers[self.customers["customer_id"] == customer_id]
        
        # Seller ids in this order
        seller_ids = items["seller_id"].unique()
        sellers = self.sellers[self.sellers["seller_id"].isin(seller_ids)]
        
        return {
            "order": order.iloc[0].to_dict(),
            "items": items.to_dict(orient="records"),
            "customer": customer.iloc[0].to_dict() if not customer.empty else {},
            "sellers": sellers.to_dict(orient="records")
        }
