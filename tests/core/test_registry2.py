"""v2.0.0 registry/2 编码契约专项：4 段码 / 双写兼容 / 无前缀泄漏。

纪律：全部绿灯自测（合成输入 + 只读真实模板），不断言主仓当前红绿。
"""
from __future__ import annotations
MODULE_ID = "core"

import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

from _base import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
_spec = importlib.util.spec_from_file_location(
    "_v20_generator", ROOT / "templates" / "build_capability_model.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

CODE_RE = re.compile(r"^[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9]*\.\d{2}$")


class CodeNamespaceTest(unittest.TestCase):
    """双写兼容：monorepo 已含项目段直用，单项目补前缀。"""

    def test_monorepo_module_keeps_namespace(self):
        self.assertEqual(gen.code_namespace("ROOT", "PROJ.DATA"), "PROJ.DATA")
        self.assertEqual(gen.code_namespace("ROOT", "MIND.DEC"), "MIND.DEC")
        self.assertEqual(gen.code_namespace("ROOT", "HELM.API"), "HELM.API")

    def test_single_project_adds_prefix(self):
        self.assertEqual(gen.code_namespace("DEMO", "DATA"), "DEMO.DATA")
        self.assertEqual(gen.code_namespace("DEMO", "CORE"), "DEMO.CORE")

    def test_no_double_prefix_leak(self):
        ns = gen.code_namespace("ROOT", "PROJ.DATA")
        self.assertFalse(ns.startswith("ROOT.ROOT"))
        self.assertFalse(ns.startswith("ROOT."))

    def test_empty_inputs_safe(self):
        self.assertEqual(gen.code_namespace("", "DATA"), "DATA")
        self.assertEqual(gen.code_namespace("DEMO", ""), "DEMO.")


class CapCodeFormatTest(unittest.TestCase):
    """4 段码：monorepo 与单项目两种 registry 都必须产出合法 4 段 cap code。"""

    def _cap_code(self, project, module, domain, seq):
        return f"{gen.code_namespace(project, module)}.{domain}.{seq:02d}"

    def test_monorepo_cap_code_is_4_segments(self):
        code = self._cap_code("ROOT", "PROJ.DATA", "READY", 1)
        self.assertEqual(code, "PROJ.DATA.READY.01")
        self.assertTrue(CODE_RE.match(code), code)

    def test_single_project_cap_code_is_4_segments(self):
        # 双写回归：示例项目 DEMO.DATA 仍合法
        code = self._cap_code("DEMO", "DATA", "READY", 1)
        self.assertEqual(code, "DEMO.DATA.READY.01")
        self.assertTrue(CODE_RE.match(code), code)

    def test_real_ledger_codes_match_namespace_rule(self):
        # 只读真实账本：所有现存 cap code 必须能被命名空间规则重建（4 段）
        # ROOT = <P>/ledger-driven-dev，主仓账本在 <P>/governance
        ledger_path = ROOT.parent / "governance" / "DECISION_LEDGER.json"
        if not ledger_path.is_file():
            self.skipTest("主仓账本不在预期路径（当前仓库即为主仓时属正常）")
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        bad = []
        for proj in (ledger.get("capability_model") or {}).get("projects") or []:
            for mod in proj.get("modules") or []:
                for cap in mod.get("caps") or []:
                    code = cap.get("code", "")
                    if not CODE_RE.match(code):
                        bad.append(code)
        self.assertEqual(bad, [], f"账本存在非 4 段码：{bad[:5]}")


class ActivationSyncTest(unittest.TestCase):
    """v2.0.0：activation 必须据真实报告同步，杜绝占位与实际相反。"""

    def test_pass_report_activates(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import work_panel as wp
        tr = {"overall": "pass", "cases": [{"id": "t1", "status": "pass"}]}
        act = wp.activation_from_report(tr)
        self.assertEqual(act["state"], "active")
        self.assertTrue(act["all_active"])

    def test_empty_or_failed_report_stays_unbound(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import work_panel as wp
        for tr in ({"overall": "pass", "cases": []},
                   {"overall": "fail", "cases": [{"id": "t", "status": "fail"}]}):
            act = wp.activation_from_report(tr)
            self.assertEqual(act["state"], "unbound")
            self.assertFalse(act["all_active"])


class NoRegressAlignedTest(unittest.TestCase):
    """修复后 no_regress 以同格式 code 直接比对，不再靠前缀剥离对齐。"""

    def test_same_format_code_no_false_downgrade(self):
        old = {"capability_model": {"projects": [{"modules": [{"caps": [
            {"code": "PROJ.DATA.READY.01", "level": 5}]}]}]}}
        new = {"projects": [{"modules": [{"caps": [
            {"code": "PROJ.DATA.READY.01", "level": 5}]}]}]}
        self.assertEqual(gen.no_regress(old, new), [])

    def test_real_downgrade_still_flagged(self):
        old = {"capability_model": {"projects": [{"modules": [{"caps": [
            {"code": "PROJ.DATA.READY.01", "level": 5}]}]}]}}
        new = {"projects": [{"modules": [{"caps": [
            {"code": "PROJ.DATA.READY.01", "level": 2}]}]}]}
        errs = gen.no_regress(old, new)
        self.assertEqual(len(errs), 1)
        self.assertIn("L5", errs[0])


if __name__ == "__main__":
    unittest.main()
