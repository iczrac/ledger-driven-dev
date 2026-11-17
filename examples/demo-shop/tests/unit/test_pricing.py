"""L3 单测：定价服务的折扣边界。"""
from src.domain.pricing import final_price


def test_discount():
    assert final_price(100.0, 0.2) == 80.0
    assert final_price(10.0, 2.0) == 0.0  # 折扣不超过本金
