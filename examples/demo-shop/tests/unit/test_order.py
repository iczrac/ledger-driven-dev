"""L3 单测：订单领域模型。"""
import unittest

from src.domain.order import Order


class OrderTest(unittest.TestCase):
    def test_payable(self):
        self.assertTrue(Order("o1", 10.0).is_payable())
        self.assertFalse(Order("o2", 0.0).is_payable())


if __name__ == "__main__":
    unittest.main()
