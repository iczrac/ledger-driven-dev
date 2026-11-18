"""升级与迁移：只读计划、人批准、备份/回滚、复验与证据重绑的负向证明。

所有用例都在临时副本上跑，绝不修改 examples/demo-shop 的真实账本。
"""
from __future__ import annotations
MODULE_ID = "meta"

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from _base import DEMO, ROOT, run_verify
from ledger_io import current_fingerprint, load_ledger, write_ledger

sys.path.insert(0, str(ROOT / "scripts"))
from upgrade import (METHOD_VERSION, POST_UPGRADE, TOOLING, apply,  # noqa: E402
                     check_definitions, plan, rollback, verify)

UPGRADE = ROOT / "scripts" / "upgrade.py"


@contextmanager
def project_copy():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        dst = tmp / "examples" / "demo-shop"
        shutil.copytree(DEMO, dst, ignore=shutil.ignore_patterns("__pycache__"))
        yield tmp, dst


def tree_hash(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}


def ledger_of(target: Path) -> dict:
    return load_ledger(target / "governance")


class UpgradeTest(unittest.TestCase):

    # ---------- 定义与计划 ----------
    def test_definitions_selfcheck(self):
        self.assertEqual(check_definitions(), [])
        self.assertEqual(plan.__name__, "plan")
        self.assertEqual(len(POST_UPGRADE), 18)
        self.assertEqual(len(TOOLING), 3)

    def test_plan_is_read_only_deterministic_and_leak_free(self):
        with project_copy() as (tmp, target):
            before = tree_hash(target)
            a = plan(target)
            b = plan(target)
            self.assertEqual(tree_hash(target), before)
            self.assertEqual(a, b)
            self.assertEqual(a["schema"], "upgrade-plan/1")
            self.assertEqual(a["from_method"], "pre-1.0.0")
            self.assertEqual(a["to_method"], METHOD_VERSION)
            self.assertFalse(a["noop"])
            self.assertTrue(a["approval_required"])
            self.assertNotIn("/Users/", json.dumps(a, ensure_ascii=False))
            self.assertNotIn(str(ROOT), json.dumps(a, ensure_ascii=False))

    def test_plan_detects_tool_drift(self):
        """U1 探针：已交付项目的工具副本漂移必须被 plan 发现。"""
        with project_copy() as (tmp, target):
            tool = target / "governance" / "verify_ledger.py"
            tool.write_text(tool.read_text(encoding="utf-8") + "\n# local patch\n",
                            encoding="utf-8")
            p = plan(target)
            row = next(r for r in p["tools"] if r["path"] == "governance/verify_ledger.py")
            self.assertEqual(row["state"], "drifted")
            self.assertIn("M3-tool-sync", [m["id"] for m in p["migrations"]])
            self.assertEqual(p["risk"], "medium")

    def test_unsupported_version_and_frozen_block(self):
        with project_copy() as (tmp, target):
            gov = target / "governance"
            d = ledger_of(target)
            d["ledger_version"] = "2.0"
            (gov / "DECISION_LEDGER.json").write_text(json.dumps(d, ensure_ascii=False))
            p = plan(target)
            self.assertIn("unsupported_ledger_version", [b["id"] for b in p["blocks"]])
            with self.assertRaises(ValueError):
                apply(target, "张三", p=p)

            d["ledger_version"] = "1.0"
            d["lifecycle"] = {"state": "frozen", "approved_by": "张三"}
            (gov / "DECISION_LEDGER.json").write_text(json.dumps(d, ensure_ascii=False))
            self.assertIn("lifecycle_not_writable",
                          [b["id"] for b in plan(target)["blocks"]])

    # ---------- 应用 ----------
    def test_apply_requires_human_approval(self):
        with project_copy() as (tmp, target):
            before = tree_hash(target)
            with self.assertRaises(ValueError):
                apply(target, "")
            self.assertEqual(tree_hash(target), before)

    def test_apply_is_approved_backed_up_and_verifiable(self):
        """T2 探针：兼容版本的升级有完整闭环，且 24 条不变量仍全绿。"""
        with project_copy() as (tmp, target):
            fp_before = current_fingerprint(ledger_of(target))
            n_events = len(ledger_of(target)["history"]["events"])
            res = apply(target, "张三")
            self.assertFalse(res["noop"])
            self.assertEqual(res["approved_by"], "张三")
            d = ledger_of(target)
            meta = d["governance_meta"]
            self.assertEqual(meta["method_version"], METHOD_VERSION)
            self.assertEqual(meta["upgraded_from"], "pre-1.0.0")
            self.assertEqual(meta["upgrade_log"][-1]["approved_by"], "张三")
            self.assertEqual(d["access"]["schema"], "access/1")
            self.assertEqual(d["access"]["agents"], [])
            self.assertEqual(current_fingerprint(d), fp_before)
            self.assertEqual(len(d["history"]["events"]), n_events)

            bdir = target / ".ledger-upgrade" / "backups" / res["backup"]
            manifest = json.loads((bdir / "manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(manifest["files"])
            for item in manifest["files"]:
                self.assertFalse(Path(item["path"]).is_absolute())
                self.assertNotIn("..", Path(item["path"]).parts)
                self.assertTrue((bdir / item["path"]).is_file())

            v = verify(target)
            self.assertEqual(v["overall"], "pass")
            self.assertTrue(v["upgrade_complete"])
            gov = target / "governance"
            r = run_verify(tmp, gov / "DECISION_LEDGER.json", gov / "registry.json",
                           gov / "index.html")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_apply_is_idempotent(self):
        with project_copy() as (tmp, target):
            first = apply(target, "张三")
            before = tree_hash(target)
            second = apply(target, "张三")
            self.assertTrue(second["noop"])
            self.assertEqual(tree_hash(target), before)
            self.assertEqual(len(ledger_of(target)["governance_meta"]["upgrade_log"]), 1)
            backups = list((target / ".ledger-upgrade" / "backups").iterdir())
            self.assertEqual(len(backups), 1)
            self.assertEqual(first["backup"], backups[0].name)

    def test_verify_flags_stale_evidence(self):
        """U2 探针：升级后改了测试源码，verify 必须拒绝宣布完成。"""
        with project_copy() as (tmp, target):
            apply(target, "张三")
            test_file = target / "tests" / "unit" / "test_order.py"
            test_file.write_text(test_file.read_text(encoding="utf-8")
                                 + "\n# changed after upgrade\n", encoding="utf-8")
            v = verify(target)
            ev = next(c for c in v["checks"] if c["id"] == "evidence_rebaseline")
            self.assertEqual(ev["status"], "warn")
            self.assertIn("run_tests.py", ev["fix"])
            self.assertFalse(v["upgrade_complete"])
            self.assertEqual(v["overall"], "pass")  # warn 不是 block，但仍不能宣布完成

    # ---------- 回滚 ----------
    def test_rollback_restores_state_and_writes_receipt(self):
        with project_copy() as (tmp, target):
            gov = target / "governance"
            original = (gov / "DECISION_LEDGER.json").read_bytes()
            res = apply(target, "张三")
            self.assertNotEqual((gov / "DECISION_LEDGER.json").read_bytes(), original)
            out = rollback(target, res["backup"], "李四")
            self.assertEqual(out["approved_by"], "李四")
            self.assertEqual((gov / "DECISION_LEDGER.json").read_bytes(), original)
            receipt = json.loads((target / ".ledger-upgrade" / "backups" / res["backup"]
                                  / "rollback-receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["approved_by"], "李四")
            self.assertNotIn("/Users/", json.dumps(receipt, ensure_ascii=False))
            with self.assertRaises(ValueError):
                rollback(target, "not-a-backup-id", "李四")
            with self.assertRaises(ValueError):
                rollback(target, res["backup"], "")

    # ---------- CLI ----------
    def test_cli_plan_json_is_deterministic_and_leak_free(self):
        with project_copy() as (tmp, target):
            cmd = [sys.executable, str(UPGRADE), "--target", str(target),
                   "plan", "--json"]
            a = subprocess.run(cmd, capture_output=True, text=True)
            b = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(a.returncode, 0, a.stderr)
            self.assertEqual(a.stdout, b.stdout)
            self.assertNotIn("/Users/", a.stdout)
            self.assertNotIn(str(ROOT), a.stdout)
            self.assertEqual(json.loads(a.stdout)["schema"], "upgrade-plan/1")

    def test_cli_apply_without_approval_is_rejected(self):
        with project_copy() as (tmp, target):
            p = subprocess.run([sys.executable, str(UPGRADE), "--target", str(target),
                                "apply", "--json"], capture_output=True, text=True)
            self.assertEqual(p.returncode, 1)
            self.assertIn("approved-by", p.stderr)


class UpgradeV130Test(unittest.TestCase):
    """v1.3.0：无实测报告的项目不得让 M8 永久 pending。"""

    def test_plan_converges_without_test_report(self):
        with project_copy() as (tmp, target):
            gov = target / "governance"
            report = gov / "test_report.json"
            if report.is_file():
                report.unlink()
            d = ledger_of(target)
            d.pop("test_results", None)
            write_ledger(gov, d)
            apply(target, "张三")
            second = plan(target)
            self.assertTrue(second["noop"], second["migrations"])
            self.assertNotIn("M8-work-panel",
                             [m["id"] for m in second["migrations"]])
            v = verify(target)
            self.assertEqual(v["summary"]["na"], 1)
            self.assertTrue(v["upgrade_complete"])

    def test_post_upgrade_report_is_generated_in_target(self):
        self.assertTrue(POST_UPGRADE[0].startswith("cd P && "))
        self.assertIn("governance/run_tests.py", POST_UPGRADE[0])
        self.assertNotIn("scripts/run_tests.py", POST_UPGRADE[0])


if __name__ == "__main__":
    unittest.main()
