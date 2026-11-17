"""L2 实现：订单领域模型。"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Order:
    order_id: str
    amount: float
    status: str = "created"
    coupon: Optional[str] = None

    def is_payable(self) -> bool:
        return self.status == "created" and self.amount > 0
