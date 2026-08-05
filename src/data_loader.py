"""
File này KHÔNG được coordinator sử dụng.

Data loader chính thức của pipeline là `src/agents/data_loader.py` (Người 1,
class DataLoader, dùng cho OrderSellerAgent). Giữ lại file này là bản nháp ban
đầu của Coordinator trước khi phát hiện Người 1 đã có module riêng — không xoá
để tránh mất lịch sử review, nhưng không import ở bất kỳ đâu trong pipeline
thật (xem src/coordinator.py).
"""
