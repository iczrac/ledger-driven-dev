"""测试架构的负向证明：清单、MODULE_ID、发现口径三方一致。"""
from __future__ import annotations
MODULE_ID = "views"

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from _base import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from test_modules import (declared, discovered, load_map, render_md,  # noqa: E402
                          target_report, validate)


class TestModulesTest(unittest.TestCase):

    def test_map_module_id_and_discovery_agree(self):
        self.assertEqual(validate(ROOT), [])
        self.assertEqual(declared(ROOT), discovered(ROOT))
        m = load_map(ROOT)
        self.assertEqual(len(m["modules"]), 6)
        for mod in m["modules"]:
            for rel in mod["files"]:
                p = ROOT / rel
                self.assertIn(f'MODULE_ID = "{mod["id"]}"',
                              p.read_text(encoding="utf-8"))

    def test_two_discovery_mechanisms_find_same_files(self):
        disc = discovered(ROOT)
        self.assertEqual(len(disc), 21)
        self.assertEqual(len(set(disc)), len(disc))
        self.assertTrue(all(f.startswith("tests/") and f.endswith(".py") for f in disc))

    def test_render_is_deterministic_and_describes_modules(self):
        md = render_md(ROOT)
        self.assertEqual(md, render_md(ROOT))
        self.assertIn("测试架构与模块映射", md)
        for mid in ("core", "meta", "views", "traceability"):
            self.assertIn(mid, md)
        self.assertIn("不要手改", md)

    def test_detects_missing_module_id_and_bad_module_name(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "scripts").mkdir()
            (root / "scripts" / "run_tests.py").write_text('"test_*.py"', encoding="utf-8")
            (root / "tests" / "platform").mkdir(parents=True)
            (root / "tests" / "platform" / "test_x.py").write_text(
                'import unittest\nclass T(unittest.TestCase):\n  def test_a(self): pass\n',
                encoding="utf-8")
            (root / "tests" / "MODULES.json").write_text(json.dumps({
                "schema": "test-modules/1", "discovery": "test_*.py",
                "modules": [{"id": "platform", "name": "x", "scope": "x",
                             "owner_scripts": ["scripts/run_tests.py"],
                             "files": ["tests/platform/test_x.py"]}],
            }, ensure_ascii=False), encoding="utf-8")
            errs = validate(root)
            self.assertTrue(any("标准库" in e for e in errs))
            self.assertTrue(any("MODULE_ID" in e for e in errs))

    def test_target_report_flags_modules_without_tests(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            gov = root / "governance"
            gov.mkdir(parents=True)
            (gov / "DECISION_LEDGER.json").write_text(json.dumps({
                "capability_model": {"projects": [{"code": "DEMO", "modules": [
                    {"code": "DEMO.CORE", "caps": [
                        {"code": "DEMO.CORE.ORDER.01",
                         "doc_index": {"unit_tests": [{"path": "tests/unit/test_order.py"}]}}]},
                    {"code": "DEMO.API", "caps": [
                        {"code": "DEMO.API.QUERY.01", "doc_index": {"unit_tests": []}}]},
                ]}]},
            }, ensure_ascii=False), encoding="utf-8")
            r = target_report(root)
            self.assertEqual(r["modules_without_tests"], ["DEMO.API"])
            self.assertEqual(r["modules"][0]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
