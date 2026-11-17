"""L2 实现：定价服务（仅骨架，对应 L2 无单测的能力点）。"""


def final_price(base: float, discount: float = 0.0) -> float:
    return round(max(base * (1 - discount), 0), 2)
