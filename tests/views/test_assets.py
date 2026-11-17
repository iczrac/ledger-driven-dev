"""资产可用性的负向证明：只读副本、清单、账本绑定与路由真实消费。"""
from __future__ import annotations
MODULE_ID = "views"

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from _base import DEMO, ROOT, demo_copy

sys.path.insert(0, str(ROOT / "scripts"))
from asset_bundle import (bundle, check_definitions, install, install_plan,  # noqa: E402
                          read_manifest, verify as assets_verify)
from route_expert import asset_root, build as route_build, check_assets, load_assets
from upgrade import apply as upgrade_apply, plan as upgrade_plan, verify as upgrade_verify


class AssetsTest(unittest.TestCase):

    def test_bundle_is_deterministic_and_complete(self):
        a, b = bundle(), bundle()
        self.assertEqual(a, b)
        self.assertEqual(len(a["digest"]), 64)
        self.assertEqual(a["counts"]["experts"], 8)
        self.assertGreaterEqual(a["counts"]["skills"], 20)
        self.assertEqual(a["file_count"], len(a["files"]))
        self.assertEqual(check_definitions(), [])
        self.assertTrue(all(f["path"].startswith(".workbuddy/") for f in a["files"]))

    def test_install_requires_human_approval_and_is_idempotent(self):
        with demo_copy() as (_tmp, _ledger, _reg, board):
            target = board.parent.parent
            with self.assertRaises(ValueError):
                install(target, apply=True)
            dry = install(target)
            self.assertFalse(dry["applied"])
            self.assertTrue(dry["changes"])
            applied = install(target, approved_by="gate-bot", apply=True)
            self.assertTrue(applied["applied"])
            self.assertTrue((target / ".workbuddy" / "skills" / "ledger-verify" / "SKILL.md").is_file())
            self.assertTrue(assets_verify(target)["ok"])
            again = install_plan(target, ROOT)
            self.assertTrue(again["noop"])

    def test_installed_copy_drift_is_detected(self):
        with demo_copy() as (_tmp, _ledger, _reg, board):
            target = board.parent.parent
            install(target, approved_by="gate-bot", apply=True)
            copy = target / ".workbuddy" / "skills" / "ledger-verify" / "SKILL.md"
            copy.write_text(copy.read_text(encoding="utf-8") + "\n# locally edited\n",
                            encoding="utf-8")
            v = assets_verify(target)
            self.assertFalse(v["ok"])
            self.assertIn("drift", [e["id"] for e in v["errors"]])
            uv = upgrade_verify(target)
            item = next(c for c in uv["checks"] if c["id"] == "installed_assets")
            self.assertEqual(item["status"], "warn")
            self.assertFalse(uv["upgrade_complete"])

    def test_manifest_binding_mismatch_is_detected(self):
        with demo_copy() as (_tmp, _ledger, _reg, board):
            target = board.parent.parent
            install(target, approved_by="gate-bot", apply=True)
            m = read_manifest(target)
            m["digest"] = "0" * 64
            (target / "governance" / "ASSET_MANIFEST.json").write_text(
                json.dumps(m, ensure_ascii=False), encoding="utf-8")
            self.assertIn("manifest_digest",
                          [e["id"] for e in assets_verify(target)["errors"]])

    def test_router_consumes_installed_assets(self):
        with demo_copy() as (_tmp, _ledger, _reg, board):
            target = board.parent.parent
            install(target, approved_by="gate-bot", apply=True, bind_ledger=False)
            root = asset_root(target)
            self.assertEqual(root.name, ".workbuddy")
            a = load_assets(root)
            self.assertEqual(a["status"], "ok")
            self.assertEqual(a["root_kind"], "installed")
            self.assertTrue(check_assets(root)["ok"])
            out = route_build(target, "升级治理骨架", "auto", "P")
            self.assertEqual(out["assets"]["root_kind"], "installed")
            self.assertEqual(out["route"]["asset_binding"]["status"], "ok")
            self.assertEqual(out["route"]["expert"], "platform-steward")
            # 少一个专家副本 → fail-closed，路由明确报 incomplete
            (root / "experts" / "platform-steward" / "EXPERT.md").unlink()
            self.assertFalse(check_assets(root)["ok"])
            self.assertEqual(route_build(target, "", "auto", "P")["assets"]["status"],
                             "incomplete")

    def test_stale_edited_copy_is_protected(self):
        with demo_copy() as (_tmp, _ledger, _reg, board):
            target = board.parent.parent
            install(target, approved_by="gate-bot", apply=True, bind_ledger=False)
            stale = ".workbuddy/skills/legacy-skill/SKILL.md"
            p = target / stale
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("user edited", encoding="utf-8")
            m = read_manifest(target)
            m["files"].append({"path": stale, "sha256": "0" * 64})
            (target / "governance" / "ASSET_MANIFEST.json").write_text(
                json.dumps(m, ensure_ascii=False), encoding="utf-8")
            self.assertIn(stale, install_plan(target, ROOT)["stale_protected"])
            install(target, approved_by="gate-bot", apply=True, bind_ledger=False)
            self.assertTrue(p.is_file())  # 被人改过的文件绝不删除

    def test_upgrade_m7_installs_and_rollback_removes_created(self):
        with demo_copy() as (_tmp, _ledger, _reg, board):
            target = board.parent.parent
            p = upgrade_plan(target)
            self.assertIn("M7-asset-install", [m["id"] for m in p["migrations"]])
            result = upgrade_apply(target, "gate-bot")
            self.assertIn("M7-asset-install", result["migrations"])
            self.assertTrue(assets_verify(target)["ok"])
            uv = upgrade_verify(target)
            self.assertEqual(next(c for c in uv["checks"]
                                  if c["id"] == "installed_assets")["status"], "pass")
            backups = sorted((target / ".ledger-upgrade" / "backups").iterdir())
            from upgrade import rollback
            rollback(target, backups[-1].name, "gate-bot")
            self.assertFalse((target / ".workbuddy" / "skills" / "ledger-verify" /
                              "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
