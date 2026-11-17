"""L1 契约：数据就绪的字段定义。"""


class DataReadyContract:
    required_fields = ("order_id", "created_at", "status")
