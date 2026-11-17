"""L3 单测：定价服务的折扣边界。"""
import unittest

from src.domain.pricing import final_price


class PricingTest(unittest.TestCase):
    def test_discount(self):
        self.assertEqual(final_price(100.0, 0.2), 80.0)
        self.assertEqual(final_price(10.0, 2.0), 0.0)  # 折扣不超过本金


if __name__ == "__main__":
    unittest.main()
