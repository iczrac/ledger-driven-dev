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
from asset_bundle import (bundle, check_claims, check_definitions, install,  # noqa: E402
                          install_plan, read_manifest, verify as assets_verify)
from route_expert import (asset_root, build as route_build, check_assets,  # noqa: E402
                          installed_manifest_paths, load_assets)
from upgrade import (apply as upgrade_apply, assets_need_m5, plan as upgrade_plan,
                     verify as upgrade_verify)
from method_assets import manifest as assets_manifest  # noqa: E402


class AssetsTest(unittest.TestCase):

    def test_bundle_is_deterministic_and_complete(self):
        a, b = bundle(), bundle()
        self.assertEqual(a, b)
        self.assertEqual(len(a["digest"]), 64)
        self.assertEqual(a["counts"]["experts"], 9)  # v2.13.0 + goal-orchestrator
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

    def test_project_owned_skills_do_not_poison_asset_check(self):
        """真实项目 .workbuddy/skills/ 自带技能时，不能把它们的 frontmatter
        当成方法论资产的缺陷（v1.2.1：真实存量项目试用发现的误判）。"""
        with demo_copy() as (_tmp, _ledger, _reg, board):
            target = board.parent.parent
            install(target, approved_by="gate-bot", apply=True, bind_ledger=False)
            own = target / ".workbuddy" / "skills" / "my-own-skill" / "SKILL.md"
            own.parent.mkdir(parents=True, exist_ok=True)
            own.write_text("---\nname: my-own-skill\n---\n# 项目自有技能，没有 description\n",
                           encoding="utf-8")
            root = asset_root(target)
            # 期望值从权威清单动态推导，避免新增技能/专家后硬编码计数再次漂移。
            counts = assets_manifest()["counts"]
            expect_skills = counts["skills"]
            expect_installed = counts["experts"] + counts["skills"]
            scope = installed_manifest_paths(root)
            self.assertEqual(len(scope), expect_installed)
            a = load_assets(root, scope)
            self.assertEqual(a["skill_count"], expect_skills)
            self.assertEqual(a["asset_count"], expect_installed)
            self.assertTrue(a["scoped"])
            res = check_assets(root)
            self.assertTrue(res["scoped"])
            self.assertTrue(res["ok"], res["errors"])
            out = route_build(target, "升级治理骨架", "auto", "P")
            self.assertEqual(out["assets"]["skill_count"], expect_skills)
            self.assertEqual(out["route"]["asset_binding"]["status"], "ok")

    def test_scoped_check_still_detects_missing_installed_asset(self):
        """按清单过滤不等于放松：清单内的副本被删仍要 fail-closed。"""
        with demo_copy() as (_tmp, _ledger, _reg, board):
            target = board.parent.parent
            install(target, approved_by="gate-bot", apply=True, bind_ledger=False)
            own = target / ".workbuddy" / "skills" / "my-own-skill" / "SKILL.md"
            own.parent.mkdir(parents=True, exist_ok=True)
            own.write_text("---\nname: my-own-skill\n---\n# local\n", encoding="utf-8")
            (target / ".workbuddy" / "skills" / "ledger-verify" / "SKILL.md").unlink()
            res = check_assets(asset_root(target))
            self.assertFalse(res["ok"])
            self.assertIn("skills/ledger-verify", res["errors"])

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

    def test_check_assets_digest_equals_bundle_digest(self):
        """同一个包只该有一个摘要：路由自检算出来的，必须等于安装器算出来的。"""
        with demo_copy() as (_tmp, _ledger, _reg, board):
            target = board.parent.parent
            install(target, approved_by="gate-bot", apply=True, bind_ledger=False)
            root = asset_root(target)
            self.assertEqual(root.name, ".workbuddy")
            res = check_assets(root)
            self.assertTrue(res["manifest_checked"])
            self.assertEqual(res["digest_algorithm"], "sha256-files-v1")
            self.assertEqual(res["digest"], bundle()["digest"])
            self.assertTrue(res["digest_match"], res["errors"])

    def test_check_assets_detects_byte_drift_against_manifest(self):
        """形态合法但字节变了，必须红：frontmatter 检查回答不了「还是不是那份」。"""
        with demo_copy() as (_tmp, _ledger, _reg, board):
            target = board.parent.parent
            install(target, approved_by="gate-bot", apply=True, bind_ledger=False)
            root = asset_root(target)
            self.assertTrue(check_assets(root)["ok"])
            p = root / "skills" / "ledger-verify" / "SKILL.md"
            p.write_text(p.read_text(encoding="utf-8") + "\n# tampered\n",
                         encoding="utf-8")
            res = check_assets(root)
            self.assertFalse(res["ok"])
            self.assertFalse(res["digest_match"])
            self.assertIn("manifest:skills/ledger-verify/SKILL.md: sha256 与清单不符（副本被改或清单过期）",
                          res["errors"])

    def test_check_assets_without_manifest_stays_form_only(self):
        """没有清单就没有账：只查形态，并显式标注未对账，不假装验过。"""
        with demo_copy() as (_tmp, _ledger, _reg, board):
            target = board.parent.parent
            install(target, approved_by="gate-bot", apply=True, bind_ledger=False)
            (target / "governance" / "ASSET_MANIFEST.json").unlink()
            res = check_assets(asset_root(target))
            self.assertFalse(res["manifest_checked"])
            self.assertIsNone(res["digest_match"])
            self.assertTrue(res["ok"])

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
            backups = sorted(p for p in (target / ".ledger-upgrade" / "backups").iterdir()
                             if p.is_dir())
            from upgrade import rollback
            rollback(target, backups[-1].name, "gate-bot")
            self.assertFalse((target / ".workbuddy" / "skills" / "ledger-verify" /
                              "SKILL.md").is_file())


class AssetClaimGuardTest(unittest.TestCase):
    """安装边界复用 spec_check 判据：假命令必须在写盘前被拦住。"""

    def make_source(self, td: Path, *, with_config: bool = True) -> Path:
        src = td / "method"
        (src / "skills" / "ghost").mkdir(parents=True, exist_ok=True)
        (src / "skills" / "ghost" / "SKILL.md").write_text(
            "---\nname: ghost\ndescription: 测试用\n---\n"
            "跑一次：`python3 scripts/ghost_missing.py`\n", encoding="utf-8")
        if with_config:
            (src / "spec_check.json").write_text(json.dumps({
                "schema": "spec-check/1",
                "claims": {"docs": ["skills/**/SKILL.md"], "exceptions": []}}),
                encoding="utf-8")
        return src

    def test_asset_claim_hit_blocks_apply_and_shows_in_dry_run(self):
        with tempfile.TemporaryDirectory() as td, demo_copy() as (_t, _l, _r, board):
            src = self.make_source(Path(td))
            target = board.parent.parent
            report = check_claims(src)
            self.assertEqual(report["hits"], 1)
            self.assertEqual(report["detail"][0]["reason"], "missing_command")
            dry = install_plan(target, src)
            self.assertEqual(dry["claim_hits"], 1)
            self.assertTrue(any("未解析命令" in e for e in check_definitions(src)))
            with self.assertRaises(ValueError) as ctx:
                install(target, approved_by="gate-bot", apply=True,
                        source_root=src, bind_ledger=False)
            self.assertIn("ghost_missing.py", str(ctx.exception))
            self.assertFalse((target / ".workbuddy" / "skills" / "ghost").exists())

    def test_real_command_and_missing_config_are_distinct(self):
        with tempfile.TemporaryDirectory() as td:
            src = self.make_source(Path(td))
            scripts = src / "scripts"
            scripts.mkdir()
            (scripts / "ghost_missing.py").write_text("print(1)\n", encoding="utf-8")
            self.assertEqual(check_claims(src)["hits"], 0)
            (src / "spec_check.json").unlink()
            bad = check_claims(src)
            self.assertEqual(bad["hits"], 1)
            self.assertEqual(bad["detail"][0]["reason"], "spec_config_unreadable")


class InstallableDigestTest(unittest.TestCase):
    """M5 只应由下游真正消费的资产变更触发；scripts/docs 变更不得造成整包重批虚警。

    双向保护：
      - 放宽侧：改 scripts/ 或 method_docs → 不触发 M5（消虚警）
      - 保护侧：改 skills/ 或 templates/ → 必须触发 M5（判定规则变了）
    """

    def test_installable_digest_excludes_scripts_and_method_docs(self):
        m = assets_manifest(ROOT)
        self.assertIn("installable_digest", m)
        self.assertNotEqual(m["digest"], m["installable_digest"])
        groups = set(m["installable_groups"])
        self.assertIn("skills", groups)
        self.assertIn("experts", groups)
        self.assertIn("templates", groups)
        self.assertIn("standard", groups)
        self.assertNotIn("scripts", groups)
        self.assertNotIn("method_docs", groups)
        # 逐档清单仍在（供可诊断化），不受分组摘要影响
        self.assertEqual(len(m["files"]), m["file_count"])

    def _m5_needed(self, target: Path) -> bool:
        p = upgrade_plan(target)
        return any((m.get("id") if isinstance(m, dict) else m) == "M5-method-assets"
                   for m in p.get("migrations", []))

    def _target_with_installable_digest(self):
        """真实 demo 副本 + apply 一次，使账本带上 installable_digest（迁移后状态）。"""
        import contextlib
        import io
        ctx = demo_copy()
        _t, _l, _r, board = ctx.__enter__()
        target = board.parent.parent
        with contextlib.redirect_stdout(io.StringIO()):
            upgrade_apply(target, approved_by="gate-bot")
        return ctx, target

    def test_scripts_change_does_not_trigger_m5(self):
        ctx, target = self._target_with_installable_digest()
        try:
            probe = ROOT / "scripts" / "board_path.py"
            original = probe.read_bytes()
            try:
                probe.write_bytes(original + b"\n# probe\n")
                self.assertFalse(self._m5_needed(target),
                                 "改 scripts/ 不应让下游整包重批")
            finally:
                probe.write_bytes(original)
        finally:
            ctx.__exit__(None, None, None)

    def test_method_docs_change_does_not_trigger_m5(self):
        ctx, target = self._target_with_installable_digest()
        try:
            docs = sorted(ROOT.glob("docs/[0-9][0-9]-*.md"))
            self.assertTrue(docs)
            probe = docs[0]
            original = probe.read_bytes()
            try:
                probe.write_bytes(original + b"\nprobe\n")
                self.assertFalse(self._m5_needed(target),
                                 "改说明文档不应让下游整包重批")
            finally:
                probe.write_bytes(original)
        finally:
            ctx.__exit__(None, None, None)

    def test_skills_change_still_triggers_m5(self):
        """保护网：判定规则变了必须重批，不得因优化而削弱。"""
        ctx, target = self._target_with_installable_digest()
        try:
            probe = ROOT / "skills" / "ledger-guard" / "SKILL.md"
            original = probe.read_bytes()
            try:
                probe.write_bytes(original + b"\nprobe\n")
                self.assertTrue(self._m5_needed(target),
                                "改 skills/ 必须触发 M5——保护网不可削弱")
            finally:
                probe.write_bytes(original)
        finally:
            ctx.__exit__(None, None, None)

    def test_templates_change_still_triggers_m5(self):
        """保护网：看板/校验模板是判定规则的一部分。"""
        ctx, target = self._target_with_installable_digest()
        try:
            probe = ROOT / "templates" / "index.html.template"
            original = probe.read_bytes()
            try:
                probe.write_bytes(original + b"\nprobe\n")
                self.assertTrue(self._m5_needed(target),
                                "改 templates/ 必须触发 M5")
            finally:
                probe.write_bytes(original)
        finally:
            ctx.__exit__(None, None, None)

    def test_legacy_ledger_falls_back_to_full_digest(self):
        """旧账本无 installable_digest 时回退全量 digest 比较——不削弱保护。"""
        cur = {"digest": "a" * 64, "installable_digest": "b" * 64}
        # 新账本：分组摘要一致 → 不需重批（即使全量 digest 不同）
        self.assertFalse(assets_need_m5(
            {"digest": "stale-full", "installable_digest": "b" * 64}, cur))
        # 新账本：分组摘要不同 → 需重批
        self.assertTrue(assets_need_m5(
            {"digest": "x", "installable_digest": "changed"}, cur))
        # 旧账本：无分组字段 → 回退全量 digest 比较。因为旧全量摘要的语义
        # 与新分组摘要不同，首次 apply 必然触发一次 M5（一次性迁移成本，
        # 写入 installable_digest 后即消失）——绝不静默放行旧账本。
        self.assertTrue(assets_need_m5({"digest": "a" * 64}, cur))
        self.assertTrue(assets_need_m5({"digest": "stale-full"}, cur))

    def test_both_digest_fields_have_full_length(self):
        m = assets_manifest(ROOT)
        self.assertEqual(len(m["digest"]), 64)
        self.assertEqual(len(m["installable_digest"]), 64)
        self.assertEqual(len(m["files"]), m["file_count"])


if __name__ == "__main__":
    unittest.main()
