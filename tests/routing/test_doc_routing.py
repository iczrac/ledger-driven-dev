"""文档生命周期路由：doc 意图识别、冲突唯一负责人与 fail-closed。"""
MODULE_ID = "routing"
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from route_expert import build, classify_intent


_TEMP_DIRS: list[str] = []


def governed_tree() -> Path:
    root = Path(tempfile.mkdtemp())
    _TEMP_DIRS.append(str(root))
    (root / "governance").mkdir()
    (root / "governance" / "DECISION_LEDGER.json").write_text(json.dumps({
        "entries": [{"id": "D-001"}], "capability_model": {"next_queue": []}}),
        encoding="utf-8")
    (root / "governance" / "registry.json").write_text(json.dumps({
        "modules": [{"code": "CORE"}]}), encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "core.py").write_text("x = 1\n", encoding="utf-8")
    return root


class DocRoutingTest(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        for path in _TEMP_DIRS:
            shutil.rmtree(path, ignore_errors=True)

    def test_doc_only_routes_ledger_steward(self):
        r = build(governed_tree(), "帮我整理文档，文档过期了", "auto", "demo")
        self.assertTrue(any(i.startswith("doc(") for i in r["intents"]))
        self.assertEqual(r["route"]["expert"], "ledger-steward")
        self.assertEqual(r["route"]["handoff"]["chain"],
                         ["ledger-steward", "loop-executor", "evidence-auditor"])
        self.assertIn("doc-lifecycle", r["route"]["skills"])
        self.assertIsNone(r["needs_clarification"])

    def test_doc_plus_code_single_writer(self):
        r = build(governed_tree(), "把文档规范化并补单测", "auto", "demo")
        self.assertTrue(any(i.startswith("doc(") for i in r["intents"]))
        self.assertTrue(any(i.startswith("code(") for i in r["intents"]))
        self.assertEqual(r["route"]["expert"], "ledger-steward")
        self.assertNotIn("src/**", r["route"]["writes"])
        self.assertIn("loop-executor", r["route"]["handoff"]["chain"])

    def test_doc_plus_verify_readonly_auditor(self):
        r = build(governed_tree(), "文档和代码对不上了，校验文档漂移", "auto", "demo")
        self.assertTrue(any(i.startswith("doc(") for i in r["intents"]))
        self.assertTrue(any(i.startswith("verify(") for i in r["intents"]))
        self.assertEqual(r["route"]["expert"], "evidence-auditor")
        self.assertEqual(r["route"]["writes"], [])

    def test_english_doc_patterns(self):
        r = build(governed_tree(), "rebuild docs, doc drift and stale suspect",
                  "auto", "demo")
        self.assertTrue(any(i.startswith("doc(") for i in r["intents"]))
        self.assertEqual(r["route"]["expert"], "ledger-steward")

    def test_fuzzy_ambiguous_no_doc_claim(self):
        r = build(governed_tree(), "整理一下那个东西", "auto", "demo")
        self.assertFalse(any(i.startswith("doc(") for i in r["intents"]))
        self.assertIsNotNone(r["needs_clarification"])

    def test_empty_intent_no_doc_claim(self):
        r = build(governed_tree(), "", "auto", "demo")
        self.assertFalse(any(i.startswith("doc(") for i in r["intents"]))
        self.assertEqual(r["route"]["expert"], "ledger-steward")

    def test_triple_conflict_fail_closed(self):
        r = build(governed_tree(), "文档规范化，补单测，校验不变量",
                  "auto", "demo")
        self.assertTrue(any(i.startswith("doc(") for i in r["intents"]))
        self.assertIsNotNone(r["needs_clarification"])
        self.assertEqual(r["route"]["expert"], "evidence-auditor")


class DocIntentPatternTest(unittest.TestCase):
    def test_doc_patterns_cover_required_terms(self):
        s = classify_intent("文檔规范化生成，过期失效漂移复核，重建索引覆盖，"
                            "suspect stale doc lifecycle rebuild docs doc drift doc trust")
        self.assertGreaterEqual(s["doc"], 8)
