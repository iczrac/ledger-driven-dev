"""成熟度分析层：健康度子维度、时间序列、差异摘要与推荐行动。

新增字段必须可复算、可校验、向后兼容；本测试先锁定数据契约，
再允许前端把同一份投影画成热力图与趋势图。
"""
from __future__ import annotations

MODULE_ID = "core"
import unittest

from _base import ROOT, load_ledger

from build_capability_model import (  # noqa: E402
    HEALTH_DIMENSION_WEIGHTS,
    HEALTH_METHOD,
    LINEAGE_SCHEMA,
    build_analytics,
    compute_health_dimensions,
    recommended_actions,
    round_half_up,
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


class HealthNaContractTest(unittest.TestCase):
    """0/0 不得记 0：分母为 0 标 n/a、排除加权并揭露覆盖度。"""

    @classmethod
    def setUpClass(cls):
        cls.ledger = load_ledger()
        cls.cm = cls.ledger["capability_model"]

    @staticmethod
    def _model(with_caps: bool = True) -> dict:
        caps = [{"code": f"EQ.MOD.{i:02d}", "name": f"c{i}",
                 "level": 5, "evidence_tier": "verified"} for i in range(1, 6)]
        return {"summary": {"evidence_freshness": "fresh"},
                "projects": ([{"code": "EQ", "modules": [
                    {"code": "EQ.MOD", "caps": caps}]}] if with_caps else [])}

    @staticmethod
    def _ledger(test_results: dict | None = None) -> dict:
        ledger = {"entries": [], "work_items": []}
        if test_results is not None:
            ledger["test_results"] = test_results
        return ledger

    def test_empty_test_cases_mark_na_and_renormalize(self):
        variants = (
            self._ledger(),
            self._ledger({"cases": [], "summary": {"total": 0, "passed": 0}}),
        )
        for ledger in variants:
            with self.subTest(has_tr="test_results" in ledger):
                health = compute_health_dimensions(self._model(), ledger)
                row = health["dimensions"]["test_pass_rate"]
                self.assertEqual(row["status"], "na")
                self.assertIsNone(row["score"])
                self.assertEqual(row["detail"], "n/a (未投影)")
                self.assertEqual(row["weight"], HEALTH_DIMENSION_WEIGHTS["test_pass_rate"])
                self.assertEqual(row["effective_weight"], 0.0)
                self.assertEqual(health["overall"], 100.0)
                self.assertEqual(health["coverage"], {
                    "applied": 4, "total": 5,
                    "na_dims": ["test_pass_rate"], "weight_base": 0.75})
                self.assertEqual(
                    health["recommendation_note"], "因測試未投影而抑制建議")
                self.assertEqual(recommended_actions(self._model(), ledger, health), [])

    def test_opted_out_projection_cases_are_not_counted(self):
        """P2：宣告 opt-out 后，即便账本残留 cases 也不得污染健康分。"""
        ledger = self._ledger({"cases": [{"status": "pass"}],
                               "summary": {"total": 1, "passed": 1}})
        ledger.setdefault("governance_meta", {})["projection_policy"] = {
            "schema": "projection-policy/1", "test_results": "opt-out",
            "reason": "消费方刻意不投影节点测试结果", "approved_by": "iczrac"}
        health = compute_health_dimensions(self._model(), ledger)
        row = health["dimensions"]["test_pass_rate"]
        self.assertEqual(row["status"], "na")
        self.assertIsNone(row["score"])
        self.assertEqual(row["detail"], "n/a (未投影)")
        self.assertEqual(row["effective_weight"], 0.0)
        self.assertEqual(health["coverage"], {
            "applied": 4, "total": 5,
            "na_dims": ["test_pass_rate"], "weight_base": 0.75})

    def test_zero_capabilities_marks_verified_na(self):
        ledger = self._ledger({"cases": [{"status": "pass"}],
                               "summary": {"total": 1, "passed": 1}})
        health = compute_health_dimensions(self._model(with_caps=False), ledger)
        row = health["dimensions"]["verified_coverage"]
        self.assertEqual(row["status"], "na")
        self.assertIsNone(row["score"])
        self.assertEqual(row["detail"], "n/a (无能力点)")
        self.assertEqual(health["overall"], 100.0)
        self.assertEqual(health["coverage"]["na_dims"], ["verified_coverage"])
        self.assertEqual(health["coverage"]["weight_base"], 0.8)

    def test_real_cases_keep_legacy_formula(self):
        health = compute_health_dimensions(self.cm, self.ledger)
        row = health["dimensions"]["test_pass_rate"]
        self.assertEqual(row["status"], "ok")
        self.assertEqual(row["score"], 100.0)
        self.assertEqual(row["detail"], "3/3")
        self.assertEqual(row["effective_weight"], row["weight"])
        self.assertEqual(health["overall"], 90.2)
        self.assertEqual(health["coverage"]["applied"], 5)
        self.assertEqual(HEALTH_DIMENSION_WEIGHTS, {
            "evidence_freshness": 0.20, "test_pass_rate": 0.25,
            "decision_backlog": 0.15, "verified_coverage": 0.20,
            "work_health": 0.20})

    def test_half_up_not_bankers_rounding(self):
        self.assertEqual(round_half_up(56.25, 1), 56.3)
        self.assertEqual(round_half_up(90.25, 1), 90.3)

    def test_t4b_static_contract_python_and_js(self):
        py = (ROOT / "templates/build_capability_model.py").read_text()
        verify = (ROOT / "templates/verify_ledger.py").read_text()
        js = (ROOT / "templates/index.html.template").read_text()
        for token in ("n/a (未投影)", "n/a (无能力点)", "effective_weight",
                      "weight_base", "na_dims", "recommendation_note"):
            self.assertIn(token, py, token)
        self.assertIn("math.floor", py)
        self.assertIn("按有效权重重正规律", HEALTH_METHOD)
        for token in ("HEALTH_NA_TEST='n/a (未投影)'",
                      "HEALTH_NA_VERIFY='n/a (无能力点)'",
                      "effective_weight", "weight_base", "na_dims",
                      "health_coverage", "測試未投影"):
            self.assertIn(token, js, token)
        self.assertIn("Math.round(n*10)/10", js)
        self.assertIn("n/a (未投影)", verify)
        self.assertIn("compute_health_dimensions", verify)


if __name__ == "__main__":
    unittest.main()
