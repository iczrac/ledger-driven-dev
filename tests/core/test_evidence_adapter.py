"""v1.8.0 起：证据适配专项（布局探测 / classname 映射 / 声明解析 / 不降级门禁）。

v2.1.0 起 hints 不再从账本派生，改由 registry 声明解析，故此处断言
「声明缺失必须被报告」与「生成器不得回读账本」。
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


class DeclaredEvidenceTest(unittest.TestCase):
    """v2.1.0：证据只从 registry 声明解析，账本不得再充当 hints 来源。"""

    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.root = Path(self.td)
        (self.root / "projects/app/tests/unit").mkdir(parents=True)
        self.test_file = self.root / "projects/app/tests/unit/test_ready.py"
        self.test_file.write_text("def test_x():\n    assert True\n")

    def test_resolves_existing_declared_path(self):
        hit, miss = gen.resolve_declared(
            self.root, ["projects/app/tests/unit/test_ready.py"], None)
        self.assertEqual(hit, ["projects/app/tests/unit/test_ready.py"])
        self.assertEqual(miss, [])

    def test_missing_declared_path_is_reported_not_dropped(self):
        hit, miss = gen.resolve_declared(self.root, ["projects/app/tests/unit/test_gone.py"], None)
        self.assertEqual(hit, [])
        self.assertEqual(miss, ["projects/app/tests/unit/test_gone.py"])

    def test_generator_no_longer_derives_hints_from_ledger(self):
        """防回归：生成器源码不得再出现「账本 → hints」这条自证回路。"""
        src = (ROOT / "templates/build_capability_model.py").read_text()
        self.assertNotIn("def evidence_hints(", src)
        self.assertNotIn("evidence_hints(ledger", src)


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


class RunTestsSourceBindingTest(unittest.TestCase):
    """v2.20.0（B 项）：run_tests.py 必须能像 import-report 一样绑定源码目录。"""

    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.root = Path(self.td)
        (self.root / "src").mkdir()
        (self.root / "tests").mkdir()
        self.src = self.root / "src" / "calc.py"
        self.src.write_text("def add(a, b):\n    return a + b\n")
        self.test = self.root / "tests" / "test_calc.py"
        self.test.write_text("def test_add():\n    assert 1 + 1 == 2\n")

    def _report(self, source_dirs=None):
        import run_tests
        old = Path.cwd()
        try:
            __import__("os").chdir(self.root)
            return run_tests.run(Path("tests"), "test_*.py", Path("."),
                                 source_dirs=source_dirs)
        finally:
            __import__("os").chdir(old)

    def test_default_binding_is_tests_only(self):
        r = self._report()
        paths = [x["path"] for x in r["evidence_binding"]["inputs"]]
        self.assertEqual(paths, ["tests/test_calc.py"])

    def test_source_dir_binding_tracks_source_changes(self):
        r1 = self._report(["src", "tests"])
        paths = {x["path"] for x in r1["evidence_binding"]["inputs"]}
        self.assertIn("src/calc.py", paths)
        self.assertIn("tests/test_calc.py", paths)
        digest1 = r1["evidence_binding"]["source_digest"]
        self.src.write_text("def add(a, b):\n    return a + b + 1\n")
        r2 = self._report(["src", "tests"])
        self.assertNotEqual(digest1, r2["evidence_binding"]["source_digest"])

    def test_missing_source_dir_fails_closed(self):
        with self.assertRaises(ValueError) as ctx:
            self._report(["does-not-exist"])
        self.assertIn("does-not-exist", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
