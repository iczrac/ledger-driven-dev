"""方法仓自身 spec_check 配置：真实配置通过 + 篡改负向证明。

设计边界：只启用本仓尚未被既有门禁覆盖的四项——版本锚、schema 本体引用、
发版标签、可执行主张。术语/派生漂移/必备文件/链接/文件布局已由 stage_hygiene、
stage_sync、stage_layout 覆盖，不在这里重复造第二套检查器；compat 需要兄弟仓，
不进本仓 CI。
"""
from __future__ import annotations
MODULE_ID = "meta"

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from _base import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import spec_check as sc  # noqa: E402

CONFIG = ROOT / "spec_check.json"


def _cfg() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


class SpecGateTest(unittest.TestCase):

    def test_real_config_passes(self):
        report = sc.run_check(ROOT)
        self.assertTrue(report["ok"], report)
        applicable = {m["metric"] for m in report["metrics"] if m["applicable"]}
        self.assertEqual(applicable, {"version", "ontology_integrity",
                                      "release_tag", "executable_claims"})
        self.assertEqual(report["na"], 5)

    def test_version_drift_hits(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "repo"
            (target / "scripts").mkdir(parents=True, exist_ok=True)
            src = (ROOT / "scripts" / "upgrade.py").read_text(encoding="utf-8")
            (target / "scripts" / "upgrade.py").write_text(
                src.replace('METHOD_VERSION = "2.29.0"', 'METHOD_VERSION = "2.28.0"'),
                encoding="utf-8")
            m = sc.check_version(target, _cfg())
            self.assertEqual(m["hits"], 1)
            self.assertEqual(m["detail"][0]["found"], "2.28.0")

    def test_bad_schema_ref_hits(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "repo"
            (target / "governance" / "onto").mkdir(parents=True, exist_ok=True)
            reg = json.loads((ROOT / "governance" / "onto" / "schemas.json").read_text())
            first = reg["schemas"][0]
            first["translates_to"] = ["schema.ghost-for-negative-test"]
            (target / "governance" / "onto" / "schemas.json").write_text(
                json.dumps(reg, ensure_ascii=False), encoding="utf-8")
            m = sc.check_ontology(target, _cfg())
            self.assertEqual(m["hits"], 1)
            self.assertEqual(m["detail"][0]["reason"], "unresolved_ref")

    def test_missing_command_hits(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "repo"
            (target / "skills" / "demo").mkdir(parents=True, exist_ok=True)
            (target / "skills" / "demo" / "SKILL.md").write_text(
                "# Demo\n\npython3 scripts/ghost.py --check-all\n", encoding="utf-8")
            cfg = {"schema": "spec-check/1",
                   "claims": {"docs": ["skills/**/SKILL.md"], "exceptions": []}}
            m = sc.check_executable_claims(target, cfg)
            self.assertEqual(m["hits"], 1)
            self.assertEqual(m["detail"][0]["reason"], "missing_command")
            self.assertEqual(m["detail"][0]["command"], "scripts/ghost.py")

    def test_exception_needs_provenance_and_not_expired(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "repo"
            (target / "skills" / "demo").mkdir(parents=True, exist_ok=True)
            (target / "skills" / "demo" / "SKILL.md").write_text(
                "python3 scripts/ghost.py\n", encoding="utf-8")
            docs = ["skills/**/SKILL.md"]
            good = {"file": "skills/demo/SKILL.md", "command": "scripts/ghost.py",
                    "reason": "外部工具，暂未随仓安装", "approved_by": "iczrac",
                    "expires_on": (date.today() + timedelta(days=1)).isoformat()}

            def result(exc):
                return sc.check_executable_claims(
                    target, {"claims": {"docs": docs, "exceptions": [exc]}})

            self.assertEqual(result(good)["hits"], 0)

            bad = dict(good)
            bad.pop("reason")
            m = result(bad)
            self.assertEqual(m["detail"][0]["reason"], "bad_exception")

            expired = dict(good, expires_on=(date.today() - timedelta(days=1)).isoformat())
            m = result(expired)
            self.assertEqual(m["detail"][0]["reason"], "expired_exception")

    def test_exception_overrides_external_miss(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            target = base / "repo"
            (target / "skills" / "demo").mkdir(parents=True, exist_ok=True)
            (base / "ledger").mkdir(parents=True, exist_ok=True)
            doc = "skills/demo/SKILL.md"
            (target / doc).write_text("python3 scripts/ghost.py\n", encoding="utf-8")
            cfg = {"claims": {
                "docs": ["skills/**/SKILL.md"],
                "external": [{"prefix": "scripts/", "repo": "../ledger",
                              "reason": "ledger 侧工具"}],
                "exceptions": [{"file": doc, "command": "scripts/ghost.py",
                                "reason": "外部工具暂缺", "approved_by": "iczrac",
                                "expires_on": (date.today() + timedelta(days=1)).isoformat()}]}}

            self.assertEqual(sc.check_executable_claims(target, cfg)["hits"], 0)

            cfg["claims"]["exceptions"][0]["expires_on"] = (
                date.today() - timedelta(days=1)).isoformat()
            m = sc.check_executable_claims(target, cfg)
            self.assertEqual(m["hits"], 1)
            self.assertEqual(m["detail"][0]["reason"], "expired_exception")

    def test_external_repo_resolves_and_missing_fails(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            target, sibling = base / "repo", base / "ledger"
            (target / "skills" / "demo").mkdir(parents=True, exist_ok=True)
            (sibling / "scripts").mkdir(parents=True, exist_ok=True)
            tool = sibling / "scripts" / "route.py"
            tool.write_text("", encoding="utf-8")
            (target / "skills" / "demo" / "SKILL.md").write_text(
                "python3 scripts/route.py --target .\n", encoding="utf-8")
            cfg = {"claims": {
                "docs": ["skills/**/SKILL.md"],
                "external": [{"prefix": "scripts/", "repo": "../ledger",
                              "reason": "ledger 侧工具"}],
                "exceptions": []}}

            self.assertEqual(sc.check_executable_claims(target, cfg)["hits"], 0)
            tool.unlink()
            m = sc.check_executable_claims(target, cfg)
            self.assertEqual(m["hits"], 1)
            self.assertEqual(m["detail"][0]["reason"], "external_command_missing")

    def test_gate_wires_spec_check(self):
        text = (ROOT / "scripts" / "check.sh").read_text(encoding="utf-8")
        self.assertIn("stage_spec(){", text)
        self.assertIn("scripts/spec_check.py --target .", text)
        self.assertIn("run '规范自查' stage_spec", text)

    def test_gate_wires_main_ledger_verify(self):
        """P1：三处静态接线 + 行为负向证明，缺一即 FAIL。"""
        text = (ROOT / "scripts" / "check.sh").read_text(encoding="utf-8")
        self.assertIn("stage_verify_main(){", text)
        self.assertIn("python3 governance/verify_ledger.py --root . --strict", text)
        wiring = "  run '主账本自校验' stage_verify_main\n"
        self.assertIn(wiring, text)
        self.assertIn("31 条三态不变量 / 主账本自校验 / 场景矩阵", text)
        # 负向证明：抽掉接线后断言必须失效，证明上述断言不是恒真。
        self.assertNotIn(wiring, text.replace(wiring, ""))
        # 行为证明：同一函式对干净主账本为 0，对写坏 analytics 非零。
        match = re.search(r"stage_verify_main\(\)\{\n(.*?)\n\}", text, re.S)
        self.assertIsNotNone(match, "找不到 stage_verify_main 函式体")
        script = ("note(){ :; }\nstage_verify_main(){\n"
                  + match.group(1) + "\n}\nstage_verify_main\n")
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            for item in ROOT.iterdir():
                if item.name in (".git", ".ledger-upgrade", "governance"):
                    continue
                os.symlink(item, tmp / item.name)
            shutil.copytree(ROOT / "governance", tmp / "governance",
                            ignore=shutil.ignore_patterns("__pycache__"))
            clean = subprocess.run(["bash", "-c", script], cwd=tmp,
                                   capture_output=True, text=True)
            self.assertEqual(clean.returncode, 0,
                             clean.stdout[-800:] + clean.stderr[-400:])
            ledger = tmp / "governance" / "DECISION_LEDGER.json"
            data = json.loads(ledger.read_text(encoding="utf-8"))
            data["capability_model"]["analytics"]["health"]["dimensions"][
                "test_pass_rate"]["detail"] = "999/999"
            ledger.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            broken = subprocess.run(["bash", "-c", script], cwd=tmp,
                                    capture_output=True, text=True)
            self.assertNotEqual(broken.returncode, 0)
            self.assertIn("analytics_test_results_detail_valid", broken.stdout)


if __name__ == "__main__":
    unittest.main()
