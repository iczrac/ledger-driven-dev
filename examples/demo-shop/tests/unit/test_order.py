"""L3 单测：订单领域模型。"""
from src.domain.order import Order


def test_payable():
    assert Order("o1", 10.0).is_payable() is True
    assert Order("o2", 0.0).is_payable() is False
