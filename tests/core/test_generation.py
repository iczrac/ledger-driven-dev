"""生成契约：编码、等级、文档索引、任务队列。"""
MODULE_ID = "core"
import re
import unittest

from _base import ROOT, GOV, load_ledger


class GenerationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = load_ledger()
        cls.cm = cls.ledger["capability_model"]
        cls.caps = [c for p in cls.cm["projects"]
                    for m in p["modules"] for c in m["caps"]]

    def test_encoding_unique_and_well_formed(self):
        pattern = re.compile(r"^[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9]*\.\d{2}$")
        codes = [c["code"] for c in self.caps]
        self.assertEqual(len(codes), 4)
        self.assertEqual(len(codes), len(set(codes)))
        for code in codes:
            self.assertRegex(code, pattern)

    def test_completion_derived_from_level(self):
        for c in self.caps:
            self.assertAlmostEqual(c["completion"], round(c["level"] / 5, 2))

    def test_levels_match_real_evidence(self):
        levels = {c["code"]: c["level"] for c in self.caps}
        self.assertEqual(levels["DEMO.DATA.READY.01"], 5)
        self.assertEqual(levels["DEMO.CORE.ORDER.01"], 5)
        self.assertEqual(levels["DEMO.CORE.PRICE.02"], 5)
        self.assertEqual(levels["DEMO.API.QUERY.01"], 2)

    def test_all_indexed_doc_paths_exist(self):
        keys = ("plans", "related_docs", "module_docs", "contracts",
                "impl", "unit_tests", "test_records")
        missing = [
            item["path"] for c in self.caps
            for k in keys for item in c["doc_index"].get(k, [])
            if not (ROOT / item["path"]).exists()
        ]
        self.assertEqual(missing, [])

    def test_next_queue_carries_confirmed_lesson(self):
        queue = self.cm["next_queue"]
        self.assertEqual(len(queue), 1)
        task = queue[0]
        self.assertEqual(task["code"], "DEMO.API.QUERY.01")
        self.assertEqual(task["level"], "L2")
        self.assertEqual(task["target_level"], "L3")
        self.assertIn("单测(L3)", task["missing_evidence"])
        self.assertEqual([x["id"] for x in task["lessons"]], ["L-001"])
        self.assertEqual(task["rank"], 1)

    def test_registry_hint_matches_test_record_name(self):
        # 这条规则已沉淀为示例经验 L-001，测试确保示例本身不违反它
        import json
        reg = json.loads((GOV / "registry.json").read_text())
        hints = [h for m in reg["modules"] for c in m["caps"]
                 if c["domain"] == "PRICE" for h in c["hints"]]
        self.assertTrue(any(h.lower() in "price_test_record.md" for h in hints))


if __name__ == "__main__":
    unittest.main()
