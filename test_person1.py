import json
from src.agents.data_loader import DataLoader
from src.agents.order_seller_agent import OrderSellerAgent

def main():
    # Khởi tạo loader (chỉ chạy 1 lần để load file CSV)
    data_dir = "data"
    loader = DataLoader(data_dir)
    
    # Khởi tạo Agent
    agent = OrderSellerAgent(loader)
    
    # Test case EC_001
    order_id = "e2a03ccf5ea816036608b2d8c3ab8e60"
    print(f"\nProcessing order: {order_id}")
    
    result = agent.process(order_id)
    
    # In ra dạng JSON đẹp để dễ kiểm tra
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
