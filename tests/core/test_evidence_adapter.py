"""v1.8.0 证据适配专项：证明布局探测 / classname 映射 / hints 派生 / 不降级门禁的判定逻辑。

纪律：全部是绿灯自测（合成输入验证判定），不断言主仓当前红绿。
"""
from __future__ import annotations
MODULE_ID = "core"

import json
import sys
import tempfile
import unittest
from pathlib import Path

from _base import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import work_panel as wp  # noqa: E402
# 用唯一别名加载模板，避免与其他测试从主仓 governance 导入同名模块冲突
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "_v18_generator", ROOT / "templates" / "build_capability_model.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


class DefaultSourceDirsTest(unittest.TestCase):

    def _tree(self):
        return Path(tempfile.mkdtemp())

    def test_single_layout_prefers_root(self):
        root = self._tree()
        (root / "src").mkdir(); (root / "tests").mkdir()
        (root / "projects" / "app" / "tests").mkdir(parents=True)
        self.assertEqual(wp.default_source_dirs(root), ["src", "tests"])

    def test_monorepo_expands_projects(self):
        root = self._tree()
        (root / "projects" / "app" / "src").mkdir(parents=True)
        (root / "projects" / "app" / "tests").mkdir(parents=True)
        dirs = wp.default_source_dirs(root)
        self.assertIn("projects/app/src", dirs)
        self.assertIn("projects/app/tests", dirs)

    def test_empty_tree_returns_empty(self):
        self.assertEqual(wp.default_source_dirs(self._tree()), [])


class ClassnameToFileTest(unittest.TestCase):

    def test_exact_basename_hit(self):
        wl = {"test_data_readiness.py": "projects/app/tests/unit/test_data_readiness.py"}
        self.assertEqual(
            wp.classname_to_file("tests.unit.test_data_readiness.Test.test_x", wl),
            "projects/app/tests/unit/test_data_readiness.py")

    def test_miss_returns_empty_not_guess(self):
        self.assertEqual(wp.classname_to_file("a.test_unknown", {"test_x.py": "p"}), "")

    def test_empty_input_safe(self):
        self.assertEqual(wp.classname_to_file("", {}), "")


class EvidenceHintsTest(unittest.TestCase):

    def test_derives_from_capability_evidence(self):
        ledger = {"capability_model": {"projects": [{
            "modules": [{"caps": [{
                "code": "APP.DATA.READY.01",
                "evidence": {
                    "unit_test": ["projects/app/tests/unit/test_ready.py"],
                    "test_record": ["projects/app/docs/test_records/READY.md"],
                },
            }]}]}]}}
        hints = gen.evidence_hints(ledger, "APP.DATA.READY.01")
        self.assertIn("test_ready", hints)
        self.assertIn("READY", hints)

    def test_missing_cap_returns_empty(self):
        self.assertEqual(gen.evidence_hints({}, "NOPE"), [])


class NoRegressTest(unittest.TestCase):

    def test_flags_downgrade(self):
        old = {"capability_model": {"projects": [{
            "modules": [{"caps": [{"code": "APP.X.01", "level": "L5"}]}]}]}}
        new = {"projects": [{"modules": [{"caps": [
            {"code": "APP.X.01", "level": "L2"}]}]}]}
        errs = gen.no_regress(old, new)
        self.assertEqual(len(errs), 1)
        self.assertIn("APP.X.01", errs[0])

    def test_same_level_passes(self):
        old = {"capability_model": {"projects": [{
            "modules": [{"caps": [{"code": "APP.X.01", "level": 3}]}]}]}}
        new = {"projects": [{"modules": [{"caps": [
            {"code": "APP.X.01", "level": 3}]}]}]}
        self.assertEqual(gen.no_regress(old, new), [])

    def test_levels_code_normalizes_string(self):
        self.assertEqual(gen.LEVELS_CODE("L5"), 5)
        self.assertEqual(gen.LEVELS_CODE(2), 2)


if __name__ == "__main__":
    unittest.main()
