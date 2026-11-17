"""L2 实现：订单查询接口。"""
from dataclasses import asdict

from src.domain.order import Order


def get_order(order_id: str) -> dict:
    # 示例实现：真实项目应接存储层
    return asdict(Order(order_id=order_id, amount=0.0))
