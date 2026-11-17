"""专家路由契约：状态识别、意图冲突、fail-closed 与确定性。"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _base import ROOT
from route_expert import SCHEMA, build, classify_intent, inspect

ROUTER = ROOT / "scripts" / "route_expert.py"


_TEMP_DIRS: list[str] = []


def make_tree(files: dict[str, str]) -> Path:
    root = Path(tempfile.mkdtemp())
    _TEMP_DIRS.append(str(root))
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return root


def governed_tree() -> Path:
    return make_tree({
        "governance/DECISION_LEDGER.json": json.dumps({
            "entries": [{"id": "D-001"}], "capability_model": {"next_queue": []}}),
        "governance/registry.json": json.dumps({"modules": [{"code": "CORE"}]}),
        "src/core.py": "x = 1\n",
    })


class RoutingTest(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        for path in _TEMP_DIRS:
            shutil.rmtree(path, ignore_errors=True)

    def test_classify_intent_scores_chinese_and_english(self):
        s = classify_intent("历史项目接手，先盘点存量代码，再跑 verify 检查门禁")
        self.assertGreater(s["adopt"], 0)
        self.assertGreater(s["verify"], 0)
        self.assertEqual(s["lesson"], 0)

    def test_greenfield_empty_dir(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = build(root, "新建项目", "auto", "demo")
            self.assertEqual(result["detected_mode"], "greenfield")
            self.assertEqual(result["route"]["expert"], "greenfield-architect")
            self.assertIsNone(result["needs_clarification"])
            self.assertIn("init_project.py", result["route"]["suggested_commands"][0])

    def test_brownfield_routes_to_archaeologist(self):
        root = make_tree({
            "src/domain/order.py": "class Order: pass\n",
            "tests/test_order.py": "def test_order(): pass\n",
            "docs/架构说明.md": "历史设计\n",
        })
        result = build(root, "接手历史项目，先盘点能力", "auto", "legacy")
        self.assertEqual(result["detected_mode"], "brownfield")
        self.assertEqual(result["route"]["expert"], "project-archaeologist")
        self.assertEqual(result["route"]["handoff"]["next_expert"], "project-archaeologist")
        self.assertTrue(result["route"]["writes"])

    def test_governed_verify_and_code_and_plan(self):
        cases = [
            ("CI 校验账本不变量", "evidence-auditor"),
            ("实现新功能并补单测", "loop-executor"),
            ("把任务卡变成决策", "ledger-steward"),
            ("记一条踩坑经验", "ledger-steward"),
            ("", "ledger-steward"),
        ]
        for intent, expected in cases:
            with self.subTest(intent=intent):
                root = governed_tree()
                result = build(root, intent, "auto", "proj")
                self.assertEqual(result["detected_mode"], "governed")
                self.assertEqual(result["route"]["expert"], expected)
                self.assertIsNone(result["needs_clarification"])

    def test_meta_intents_route_to_platform_steward(self):
        for intent in ("升级治理骨架", "接入 agent 并注册权限", "回滚升级"):
            with self.subTest(intent=intent):
                root = governed_tree()
                result = build(root, intent, "auto", "proj")
                self.assertEqual(result["route"]["expert"], "platform-steward")
                self.assertIn("upgrade.py",
                              " ".join(result["route"]["suggested_commands"]))
                self.assertTrue(any("approved-by" in c
                                    for c in result["route"]["handoff"]["stop_if"]))

    def test_frozen_state_still_beats_meta_intent(self):
        root = make_tree({
            "governance/DECISION_LEDGER.json": json.dumps({
                "entries": [{"id": "D-001"}], "capability_model": {"next_queue": []},
                "lifecycle": {"state": "frozen", "approved_by": "张三"}}),
            "governance/registry.json": json.dumps({"modules": [{"code": "CORE"}]}),
        })
        result = build(root, "升级治理骨架", "auto", "proj")
        self.assertEqual(result["route"]["expert"], "release-steward")
        self.assertTrue(result["route"]["blocked"])

    def test_corrupt_ledger_is_fail_closed(self):
        root = make_tree({"governance/DECISION_LEDGER.json": "{not json"})
        result = build(root, "实现功能并写决策", "auto", "proj")
        self.assertEqual(result["detected_mode"], "corrupt")
        self.assertEqual(result["route"]["expert"], "evidence-auditor")
        self.assertTrue(result["route"]["blocked"])
        self.assertIn("禁止任何写入", "；".join(result["route"]["handoff"]["stop_if"]))

    def test_conflicting_intents_ask_for_clarification(self):
        root = governed_tree()
        result = build(root, "新建项目并且校验账本还要实现功能", "auto", "proj")
        self.assertIsNotNone(result["needs_clarification"])
        self.assertGreaterEqual(len(result["needs_clarification"]["options"]), 2)

    def test_explicit_mode_conflict_asks_question(self):
        root = make_tree({"src/a.py": "x = 1\n"})
        result = build(root, "", "greenfield", "legacy")
        self.assertEqual(result["route"]["expert"], "greenfield-architect")
        self.assertIsNotNone(result["needs_clarification"])
        self.assertIn("governance/", "；".join(result["route"]["handoff"]["stop_if"]))

    def test_partial_state_does_not_overwrite_existing_files(self):
        root = make_tree({
            "governance/registry.json": json.dumps({"modules": []}),
            "src/a.py": "x = 1\n",
        })
        result = build(root, "", "auto", "legacy")
        self.assertEqual(result["detected_mode"], "partial")
        self.assertEqual(result["route"]["expert"], "project-archaeologist")
        self.assertIn("registry.json", "；".join(result["route"]["preconditions"]))

    def test_cli_json_is_deterministic_and_leak_free(self):
        root = governed_tree()
        cmd = [sys.executable, str(ROUTER), "--target", str(root),
               "--intent", "校验账本", "--json"]
        a = subprocess.run(cmd, capture_output=True, text=True, check=True)
        b = subprocess.run(cmd, capture_output=True, text=True, check=True)
        self.assertEqual(a.stdout, b.stdout)
        data = json.loads(a.stdout)
        self.assertEqual(data["schema"], SCHEMA)
        self.assertNotIn("/Users/", a.stdout)
        self.assertNotIn(str(ROOT), a.stdout)

    def test_inspect_counts_are_bounded(self):
        root = make_tree({"src/a.py": "x=1\n"})
        facts = inspect(root, max_files=0)
        self.assertTrue(facts["counts"]["truncated"])
        self.assertEqual(facts["counts"]["scanned"], 0)


if __name__ == "__main__":
    unittest.main()
