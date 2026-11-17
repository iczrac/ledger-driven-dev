"""L3 单测：数据就绪契约。"""
import unittest

from src.contracts.data_ready import DataReadyContract


class DataReadyTest(unittest.TestCase):
    def test_required_fields(self):
        self.assertIn("order_id", DataReadyContract.required_fields)


if __name__ == "__main__":
    unittest.main()
