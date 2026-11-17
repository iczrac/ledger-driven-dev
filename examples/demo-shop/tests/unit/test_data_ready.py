"""L3 单测：数据就绪契约。"""
from src.contracts.data_ready import DataReadyContract


def test_required_fields():
    assert "order_id" in DataReadyContract.required_fields
