"""声明驱动证据契约（v2.1.0）：账本不得再充当自己的证据来源。

背景：v1.8.0 让生成器从账本既有 evidence 派生 hints，形成
「账本 → hints → 证据 → 账本」的闭环。后果是把账本证据抹空后重算，
20 个 L5 全部塌成 L2——账本不是仓库的函数，而是自身的函数。

这组用例把修复钉住：
1) 等级只由 registry 声明 + 真实文件决定；
2) 声明失效必须降级，不静默保留；
3) 测试扫描不得跨项目；
4) --check 的差异比较能发现漂移。
"""
MODULE_ID = "core"

import tempfile
import unittest
from pathlib import Path

from _base import ROOT  # noqa: F401  确保 sys.path 指向 templates/

import build_capability_model as B


class DeclaredEvidenceTest(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="declared-"))
        root = self.tmp
        (root / "src/domain").mkdir(parents=True)
        (root / "src/domain/order.py").write_text("X = 1\n")
        (root / "tests/unit").mkdir(parents=True)
        (root / "tests/unit/test_order.py").write_text("def test_x():\n    assert 1\n")
        self.cfg = {
            "code": "APP", "root": ".", "governance_gate": False,
            "contracts_dir": "src/contracts", "unit_test_dir": "tests",
            "test_record_dir": "docs/test_records", "docs_dir": "docs",
            "governance_dir": "governance",
        }
        self.cap = {
            "name": "订单", "domain": "ORDER",
            "impl": ["src/domain/order.py"],
            "tests": ["tests/unit/test_order.py"],
        }

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _registry(self):
        return {"project": dict(self.cfg), "modules": [
            {"code": "CORE", "name": "核心", "src": ["src/"],
             "caps": [dict(self.cap)]},
        ]}

    def test_declared_test_drives_level_three(self):
        declared, miss = B.resolve_declared(self.tmp, self.cap["tests"], None)
        self.assertEqual(miss, [])
        level, ev = B.judge_level(
            self.tmp, self.tmp, "", self.cfg, self.cap["impl"], [],
            declared_tests=declared)
        self.assertEqual(level, 3)
        self.assertEqual(ev["unit_test"], ["tests/unit/test_order.py"])

    def test_missing_declared_test_is_reported_and_downgrades(self):
        """声明了不存在的测试：必须报告缺失，并按缺失处理（不得仍算 L3）。"""
        declared, miss = B.resolve_declared(
            self.tmp, ["tests/unit/test_gone.py"], None)
        self.assertEqual(declared, [])
        self.assertEqual(miss, ["tests/unit/test_gone.py"])
        level, ev = B.judge_level(
            self.tmp, self.tmp, "", self.cfg, self.cap["impl"], [],
            declared_tests=declared)
        self.assertEqual(level, 2)
        self.assertEqual(ev["unit_test"], [])

    def test_ledger_evidence_no_longer_influences_result(self):
        """同一 registry + 同一仓库，账本内容不同不得改变派生结果。"""
        cfg = self._registry()
        empty = {}
        with_stale = {"capability_model": {"projects": [{"modules": [{"caps": [{
            "code": "APP.CORE.ORDER.01",
            "evidence": {"unit_test": ["tests/unit/test_other_thing.py"]},
        }]}]}]}}

        def levels(ledger):
            model = B.build(self.tmp, cfg, ledger, test_report=None, scope=None)
            return {c["code"]: (c["level"], tuple(c["evidence"]["unit_test"]))
                    for p in model["projects"] for m in p["modules"] for c in m["caps"]}

        self.assertEqual(levels(empty), levels(with_stale))
        self.assertEqual(levels(empty)["APP.CORE.ORDER.01"][0], 3)

    def test_hint_scan_is_scoped_to_own_project(self):
        """两个项目有同名测试时，A 项目的能力不得拿 B 项目的测试当证据。"""
        import shutil
        root = Path(tempfile.mkdtemp(prefix="crossproj-"))
        self.addCleanup(shutil.rmtree, root, True)
        for proj in ("a1", "a2"):
            (root / f"projects/{proj}/src").mkdir(parents=True, exist_ok=True)
            (root / f"projects/{proj}/src/order.py").write_text("X = 1\n")
            (root / f"projects/{proj}/tests/unit").mkdir(parents=True, exist_ok=True)
            (root / f"projects/{proj}/tests/unit/test_order.py").write_text(
                "def test_x():\n    assert 1\n")
        cfg = dict(self.cfg, unit_test_dir="tests")
        level, ev = B.judge_level(
            root, root, "", cfg, ["projects/a1/src/order.py"], ["order"])
        self.assertEqual(level, 3)
        self.assertEqual(ev["unit_test"], ["projects/a1/tests/unit/test_order.py"])

    def test_diff_projects_flags_drift(self):
        def cap(level, tests):
            return {"code": "APP.CORE.ORDER.01", "level": level,
                    "evidence_tier": "declared",
                    "evidence": {"impl": [], "unit_test": tests,
                                 "test_record": []}}
        proj = lambda c: [{"modules": [{"code": "APP.CORE", "caps": [c],
                                        "component_tree": [], "doc_index": {}}]}]
        self.assertEqual(B.diff_projects(proj(cap(3, ["a.py"])), proj(cap(3, ["a.py"]))), [])
        drift = B.diff_projects(proj(cap(3, ["a.py"])), proj(cap(2, [])))
        self.assertEqual(len(drift), 1)
        self.assertIn("APP.CORE.ORDER.01", drift[0])


if __name__ == "__main__":
    unittest.main()
