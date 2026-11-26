"""v1.1.0 三项契约的负向证明：资产绑定、看板骨架、规模预算。

覆盖的是「能不能发现漂移」，不是「 happy path 能跑」：
  - 专家/技能/模板/文档变了，升级计划必须要求重新批准；
  - 项目手改 CSS/DOM，骨架摘要必须变，且归一化后数据仍等价；
  - 项目变大时，固定的是治理文件数，报警的是体积与 DOM。
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
from pathlib import Path

from _base import DEMO, ROOT, demo_copy
from board_contract import (board_digest, check as board_check, normalize_board,
                            skeleton_digest, template_digest)
from ledger_io import board_synced, load_ledger, write_ledger
from method_assets import check as assets_check
from method_assets import manifest as assets_manifest
from scale_budget import render_limit, report as budget_report
from scale_probe import probe
from upgrade import (METHOD_VERSION, POST_UPGRADE, PRE_UPGRADE, apply, plan,  # noqa: E402
                     verify)

SCRIPTS = ROOT / "scripts"


class AssetsTest(unittest.TestCase):

    def test_manifest_is_deterministic_and_grouped(self):
        a, b = assets_manifest(), assets_manifest()
        self.assertEqual(a, b)
        self.assertEqual(len(a["digest"]), 64)
        self.assertGreaterEqual(a["counts"]["experts"], 8)
        self.assertGreaterEqual(a["counts"]["skills"], 14)
        self.assertGreaterEqual(a["counts"]["templates"], 3)
        self.assertEqual(a["file_count"], len(a["files"]))
        self.assertTrue(all(not Path(f["path"]).is_absolute() for f in a["files"]))

    def test_digest_tracks_asset_content(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for rel in ("experts/x/EXPERT.md", "skills/x/SKILL.md", "scripts/a.py",
                        "templates/t.html.template", "docs/01-x.md", "docs/STANDARD.md"):
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("v1", encoding="utf-8")
            first = assets_manifest(root)["digest"]
            (root / "skills/x/SKILL.md").write_text("v2", encoding="utf-8")
            self.assertNotEqual(first, assets_manifest(root)["digest"])

    def test_check_rejects_incomplete_asset_set(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "experts" / "x").mkdir(parents=True)
            (root / "experts" / "x" / "EXPERT.md").write_text("x", encoding="utf-8")
            r = assets_check(root)
            self.assertFalse(r["ok"])
            self.assertTrue(any("skills" in e for e in r["errors"]))

    def test_upgrade_binds_assets_and_detects_drift(self):
        with demo_copy() as (tmp, ledger_path, _reg, board_path):
            target = board_path.parent.parent
            p = plan(target)
            self.assertIn("M5-method-assets", [m["id"] for m in p["migrations"]])
            self.assertEqual(p["assets"]["digest"], assets_manifest()["digest"])
            apply(target, "张三")
            d = load_ledger(target / "governance")
            meta = d["governance_meta"]
            self.assertEqual(meta["method_version"], METHOD_VERSION)
            self.assertEqual(meta["method_assets"]["digest"], assets_manifest()["digest"])
            self.assertEqual(meta["board_skeleton"]["digest"], template_digest())
            self.assertTrue(verify(target)["upgrade_complete"])

            # 模拟「方法论仓库发了新版、项目账本还记着旧资产」
            meta["method_assets"]["digest"] = "0" * 64
            write_ledger(target / "governance", d)  # 只改资产摘要，别顺手弄脏 EMBED
            v = verify(target)
            item = next(c for c in v["checks"] if c["id"] == "method_assets")
            self.assertEqual(item["status"], "warn")
            self.assertFalse(v["upgrade_complete"])
            self.assertIn("M5-method-assets", [m["id"] for m in plan(target)["migrations"]])

    def test_post_upgrade_covers_all_three_contracts(self):
        joined = " ".join(POST_UPGRADE)
        for name in ("board_contract.py", "scale_budget.py", "method_assets.py"):
            self.assertIn(name, joined)
        self.assertEqual(len(POST_UPGRADE), 19)
        self.assertEqual(len(PRE_UPGRADE), 1)


class BoardTest(unittest.TestCase):

    def _html(self, css: str = "body{}", embed: str = "{}") -> str:
        return (f"<html><head><style>{css}</style></head><body>"
                f'<div id="stats"></div><div id="legend"></div>'
                f'<div id="list"></div><div id="foot"></div><input id="q">'
                f"<script>const EMBED = {embed};\nlet DATA = EMBED;</script></body></html>")

    def test_digest_ignores_embed_data_but_detects_css(self):
        a = self._html(embed='{"entries":[1]}')
        b = self._html(embed='{"entries":[1,2,3]}')
        self.assertEqual(skeleton_digest(a), skeleton_digest(b))
        self.assertNotEqual(skeleton_digest(a), skeleton_digest(self._html(css="body{color:red}")))
        with self.assertRaises(ValueError):
            skeleton_digest("<html></html>")

    def test_demo_board_uses_authoritative_template(self):
        r = board_check(DEMO)
        self.assertTrue(r["match"], r["reason"])
        self.assertEqual(r["board_digest"], template_digest())
        self.assertEqual(r["layout"]["missing_ids"], [])
        self.assertGreater(r["layout"]["style_bytes"], 1000)

    def test_normalize_defaults_to_dry_run_and_requires_approval(self):
        with demo_copy() as (_tmp, _l, _r, board_path):
            gov, target = board_path.parent, board_path.parent.parent
            before = hashlib.sha256(board_path.read_bytes()).hexdigest()
            ledger = load_ledger(gov)
            res = normalize_board(gov, ledger)
            self.assertFalse(res["applied"])
            self.assertEqual(hashlib.sha256(board_path.read_bytes()).hexdigest(), before)
            with self.assertRaises(ValueError):
                normalize_board(gov, ledger, apply=True, approved_by="")

    def test_normalize_repairs_css_drift_without_touching_data(self):
        with demo_copy() as (_tmp, _l, _r, board_path):
            gov, target = board_path.parent, board_path.parent.parent
            html = board_path.read_text(encoding="utf-8")
            board_path.write_text(html.replace(":root{", ":root{--hack:1;"), encoding="utf-8")
            drift = board_check(target)
            self.assertFalse(drift["match"])
            self.assertEqual(drift["layout"]["missing_ids"], [])

            ledger = load_ledger(gov)
            out = normalize_board(gov, ledger, approved_by="张三", apply=True,
                                  backup_root=None)
            self.assertTrue(out["applied"])
            self.assertEqual(out["after_digest"], template_digest())
            self.assertTrue(board_check(target)["match"])
            self.assertTrue(board_synced(gov, ledger))
            self.assertNotIn("--hack:1", board_path.read_text(encoding="utf-8"))

    def test_missing_anchor_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            gov = target / "governance"
            gov.mkdir()
            (gov / "index.html").write_text(
                self._html().replace('<div id="stats"></div>', ""), encoding="utf-8")
            r = board_check(target)
            self.assertIn("stats", r["layout"]["missing_ids"])
            self.assertFalse(r["match"])

    def test_drift_is_part_of_the_upgrade_plan(self):
        with demo_copy() as (_tmp, _l, _r, board_path):
            target = board_path.parent.parent
            html = board_path.read_text(encoding="utf-8")
            board_path.write_text(html.replace("</style>", "/*fork*/</style>"),
                                  encoding="utf-8")
            p = plan(target)
            self.assertIn("M6-board-skeleton", [m["id"] for m in p["migrations"]])
            self.assertEqual(p["risk"], "medium")
            self.assertFalse(p["board"]["match"])
            apply(target, "张三")
            self.assertTrue(board_check(target)["match"])
            self.assertTrue(plan(target)["noop"])
            self.assertTrue(verify(target)["upgrade_complete"])

    def test_cli_check_fails_on_drift(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            gov = target / "governance"
            gov.mkdir()
            (gov / "index.html").write_text(self._html(), encoding="utf-8")
            p = subprocess.run([sys.executable, str(SCRIPTS / "board_contract.py"),
                                "--target", str(target), "check", "--json"],
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 1)
            self.assertFalse(json.loads(p.stdout)["match"])


class BudgetTest(unittest.TestCase):

    def test_render_limit_is_read_from_template(self):
        self.assertEqual(render_limit(), 200)
        self.assertIn("const PAGE_SIZE=200;",
                      (ROOT / "templates" / "index.html.template").read_text(encoding="utf-8"))

    def test_demo_budget_is_clean_and_layout_is_fixed(self):
        r = budget_report(DEMO)
        self.assertEqual(r["schema"], "scale-budget/1")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["target"], ".")
        self.assertLess(r["metrics"]["governance_files"], 20)
        self.assertIn("固定", r["fixed_layout"]["note"])
        self.assertEqual(r["metrics"]["render_page_size"], 200)

    def test_thresholds_flag_oversized_project(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            gov = target / "governance"
            gov.mkdir()
            ledger = {"ledger_version": "1.0", "entries": [{"id": f"D-{i}"} for i in range(3000)],
                      "history": {"events": [{"seq": i, "state_digest": {}} for i in range(600)]}}
            (gov / "DECISION_LEDGER.json").write_text(
                json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
            r = budget_report(target)
            self.assertIn(r["status"], ("warn", "exceed"))
            ids = {b["id"] for b in r["budgets"] if b["status"] != "ok"}
            self.assertTrue(ids & {"entries", "history_events", "render_cards"})
            p = subprocess.run([sys.executable, str(SCRIPTS / "scale_budget.py"),
                                "--target", str(target), "--check", "--strict"],
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 2)

    def test_probe_shows_file_count_stays_fixed(self):
        small = probe({"mods": 3, "caps_per": 5, "files": 40, "entries": 10, "events": 2})
        larger = probe({"mods": 3, "caps_per": 5, "files": 160, "entries": 10, "events": 2})
        self.assertTrue(small["ok"] and larger["ok"], small.get("error") or larger.get("error"))
        self.assertEqual(small["products"]["governance_files"],
                         larger["products"]["governance_files"])
        self.assertGreater(larger["products"]["project_files"],
                           small["products"]["project_files"])
        self.assertEqual(small["model"]["capabilities"], larger["model"]["capabilities"])


class BoardPathTest(unittest.TestCase):
    """看板路径解析层：规范名识别、迁移策略、全路径键（防同名 slug 串味）。"""

    def test_canonical_names_of_four_boards(self):
        import board_path as bp
        self.assertEqual(bp.canonical_filename(ROOT.parent), "system.html")
        self.assertEqual(bp.canonical_filename(ROOT), "ledger-driven-dev.html")
        self.assertEqual(bp.canonical_filename(ROOT.parent / "julia-dev-squad"),
                         "julia-dev-squad.html")
        self.assertEqual(bp.canonical_filename(DEMO), "demo-shop.html")
        self.assertTrue(bp.is_system_governance(ROOT.parent / "governance"))
        self.assertFalse(bp.is_system_governance(ROOT / "governance"))

    def test_legacy_policy_keeps_behavior_unchanged(self):
        import board_path as bp
        old = bp.POLICY
        try:
            bp.POLICY = "legacy"
            for root in (ROOT.parent, ROOT, DEMO):
                self.assertEqual(bp.filename_for(root), bp.LEGACY_FILENAME)
                self.assertEqual(bp.resolve(root).name, "index.html")
        finally:
            bp.POLICY = old

    def test_full_path_key_prevents_same_slug_cross_talk(self):
        import board_path as bp
        old = bp.POLICY
        try:
            bp.POLICY = "compatible"
            with tempfile.TemporaryDirectory() as td:
                roots = []
                for parent_name in ("alpha", "beta"):
                    root = Path(td) / parent_name / "examples" / "demo-shop"
                    (root / "governance").mkdir(parents=True)
                    (root / "governance" / "DECISION_LEDGER.json").write_text("{}", encoding="utf-8")
                    (root / "governance" / "demo-shop.html").write_text("x", encoding="utf-8")
                    roots.append(root)
                self.assertEqual(bp.canonical_filename(roots[0]),
                                 bp.canonical_filename(roots[1]))
                self.assertNotEqual(bp.resolve(roots[0]), bp.resolve(roots[1]))
                for root in roots:
                    self.assertEqual(bp.resolve(root), root / "governance" / "demo-shop.html")
        finally:
            bp.POLICY = old

    def test_compatible_policy_falls_back_to_legacy_only_when_new_missing(self):
        import board_path as bp
        old = bp.POLICY
        try:
            bp.POLICY = "compatible"
            with tempfile.TemporaryDirectory() as td:
                root = Path(td) / "demo-shop"
                gov = root / "governance"
                gov.mkdir(parents=True)
                (gov / "DECISION_LEDGER.json").write_text("{}", encoding="utf-8")
                self.assertEqual(bp.filename_for(root), "demo-shop.html")
                (gov / "index.html").write_text("old", encoding="utf-8")
                self.assertEqual(bp.filename_for(root), "index.html")
                (gov / "demo-shop.html").write_text("new", encoding="utf-8")
                self.assertEqual(bp.filename_for(root), "demo-shop.html")
        finally:
            bp.POLICY = old

    def test_cli_returns_single_line_for_shell(self):
        p = subprocess.run([sys.executable, str(SCRIPTS / "board_path.py"),
                            "--target", str(DEMO), "--filename"],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip(), "index.html")


if __name__ == "__main__":
    unittest.main()
