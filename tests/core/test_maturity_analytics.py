"""成熟度分析层：健康度子维度、时间序列、差异摘要与推荐行动。

新增字段必须可复算、可校验、向后兼容；本测试先锁定数据契约，
再允许前端把同一份投影画成热力图与趋势图。
"""
from __future__ import annotations

MODULE_ID = "core"
import unittest

from _base import load_ledger

from build_capability_model import (  # noqa: E402
    HEALTH_DIMENSION_WEIGHTS,
    LINEAGE_SCHEMA,
    build_analytics,
    compute_health_dimensions,
)


class MaturityAnalyticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = load_ledger()
        cls.cm = cls.ledger["capability_model"]
        cls.caps = {
            c["code"]: c
            for p in cls.cm.get("projects", [])
            for m in p.get("modules", [])
            for c in m.get("caps", [])
        }

    def test_health_dimensions_are_precomputed_and_bounded(self):
        health = compute_health_dimensions(self.cm, self.ledger)
        self.assertEqual(set(health["dimensions"]), set(HEALTH_DIMENSION_WEIGHTS))
        self.assertAlmostEqual(sum(HEALTH_DIMENSION_WEIGHTS.values()), 1.0)
        for name, row in health["dimensions"].items():
            self.assertIn("score", row, name)
            self.assertGreaterEqual(row["score"], 0, name)
            self.assertLessEqual(row["score"], 100, name)
        self.assertGreaterEqual(health["overall"], 0)
        self.assertLessEqual(health["overall"], 100)

    def test_analytics_has_series_change_summary_and_actions(self):
        health = compute_health_dimensions(self.cm, self.ledger)
        analytics = build_analytics(self.cm, self.ledger, health)
        self.assertEqual(analytics["schema"], "maturity-analytics/1")
        by_code = analytics["maturity"]
        self.assertTrue(by_code)
        for code, row in by_code.items():
            self.assertIn(code, self.caps, code)
            self.assertTrue(row["series"], code)
            self.assertEqual(row["series"][-1]["level"], self.caps[code]["level"], code)
            self.assertEqual(row["series"][-1]["tier"], self.caps[code]["evidence_tier"], code)
        change = analytics["change_summary"]
        self.assertIn("from_fingerprint", change)
        self.assertIn("to_fingerprint", change)
        self.assertIn("level_transitions", change)
        self.assertTrue(analytics["recommended_actions"])
        for action in analytics["recommended_actions"]:
            self.assertIn(action["code"], self.caps)
            self.assertGreaterEqual(action["health_gain"], 0)
            self.assertTrue(action["action"])

    def test_d3_projection_is_tree_shaped_and_traceable(self):
        """v2.12.0：D3 消费的是预计算树与时间轴，不是前端自造事实。"""
        health = compute_health_dimensions(self.cm, self.ledger)
        analytics = build_analytics(self.cm, self.ledger, health)
        lineage = analytics["lineage"]
        self.assertEqual(lineage["schema"], LINEAGE_SCHEMA)
        self.assertEqual(set(lineage["trees"]), set(self.caps))
        for code, tree in lineage["trees"].items():
            self.assertEqual(tree["kind"], "capability")
            self.assertEqual(tree["status"]["level"], self.caps[code]["level"])
            ids, states = set(), 0
            stack = [tree]
            while stack:
                node = stack.pop()
                self.assertIn(node["kind"], ("capability", "decision", "evidence", "state"))
                self.assertNotIn(node["id"], ids, code)
                ids.add(node["id"])
                if node["kind"] == "state":
                    states += 1
                    self.assertEqual(node["level"], self.caps[code]["level"])
                    self.assertEqual(node["tier"], self.caps[code]["evidence_tier"])
                stack.extend(node.get("children") or [])
            self.assertEqual(states, 1, code)

        events = (self.ledger.get("history") or {}).get("events") or []
        timeline = analytics["timeline"]
        self.assertEqual(len(timeline), len(events))
        self.assertEqual([p["seq"] for p in timeline],
                         sorted(p["seq"] for p in timeline))
        for point in timeline:
            self.assertIn("fingerprint", point)
            self.assertIsInstance(point["change_count"], int)

    def test_next_queue_carries_health_impact(self):
        for task in self.cm.get("next_queue", []):
            self.assertIn("health_impact", task, task["code"])
            self.assertGreaterEqual(task["health_impact"], 0)


if __name__ == "__main__":
    unittest.main()
