"""生命周期状态机专项：冻结 / 归档 / 退役 / 任务领用。"""
from __future__ import annotations
MODULE_ID = "meta"

import json
import subprocess
import sys
import unittest
from pathlib import Path

from _base import ROOT, demo_copy, run_verify
from lifecycle import apply, status

LC = ROOT / "scripts" / "lifecycle.py"


def cli(proj: Path, action: str, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(LC), "--target", str(proj), action, *extra],
                          capture_output=True, text=True)


class LifecycleTest(unittest.TestCase):
    def test_freeze_requires_active_and_records_reason(self):
        d = {"entries": []}
        d, msg = apply(d, "freeze", reason="发布窗口", actor="release-bot")
        self.assertEqual(d["lifecycle"]["state"], "frozen")
        self.assertEqual(d["lifecycle"]["reason"], "发布窗口")
        self.assertEqual(d["lifecycle"]["log"][0]["action"], "freeze")
        self.assertIn("冻结", msg)
        with self.assertRaises(ValueError):
            apply(d, "freeze", reason="重复冻结")

    def test_unfreeze_requires_human_approval(self):
        d, _ = apply({"entries": []}, "freeze", reason="x")
        with self.assertRaises(ValueError):
            apply(d, "unfreeze")
        d, _ = apply(d, "unfreeze", approved_by="张三")
        self.assertEqual(d["lifecycle"]["state"], "active")
        self.assertEqual(d["lifecycle"]["approved_by"], "张三")

    def test_archive_is_terminal(self):
        d, _ = apply({"entries": []}, "archive", approved_by="张三", reason="交付完成")
        self.assertEqual(d["lifecycle"]["state"], "archived")
        with self.assertRaises(ValueError):
            apply(d, "unfreeze", approved_by="张三")
        with self.assertRaises(ValueError):
            apply(d, "claim", code="DEMO.CORE.ORDER.01", actor="ai-1")
        self.assertFalse(status(d)["writable"])

    def test_archive_without_approval_rejected(self):
        with self.assertRaises(ValueError):
            apply({"entries": []}, "archive")

    def test_retire_validates_code_and_deduplicates(self):
        d, msg = apply({"entries": []}, "retire", code="DEMO.CORE.ORDER.01",
                       reason="被统一订单服务取代", superseded_by="DEMO.CORE.ORDER.02")
        self.assertEqual(d["retired_caps"][0]["superseded_by"], "DEMO.CORE.ORDER.02")
        self.assertIn("registry.json", msg)
        with self.assertRaises(ValueError):
            apply(d, "retire", code="DEMO.CORE.ORDER.01")
        with self.assertRaises(ValueError):
            apply(d, "retire", code="bad-code")
        d, _ = apply(d, "restore", code="DEMO.CORE.ORDER.01")
        self.assertEqual(d["retired_caps"], [])

    def test_claim_release_and_duplicate_claim_rejected(self):
        d, _ = apply({"entries": []}, "claim", code="DEMO.API.QUERY.01", actor="ai-1")
        d, msg = apply(d, "claim", code="DEMO.API.QUERY.01", actor="ai-1")
        self.assertIn("幂等", msg)
        with self.assertRaises(ValueError):
            apply(d, "claim", code="DEMO.API.QUERY.01", actor="ai-2")
        d, _ = apply(d, "release", code="DEMO.API.QUERY.01", actor="ai-1")
        self.assertEqual(status(d)["claims"], [])

    def test_freeze_blocks_generator(self):
        with demo_copy() as (tmp, ledger, reg, board):
            proj = tmp / "examples" / "demo-shop"
            self.assertEqual(cli(proj, "freeze", "--reason", "发布窗口").returncode, 0)
            p = subprocess.run(
                [sys.executable, str(proj / "governance" / "build_capability_model.py"),
                 "--root", str(tmp), "--registry", str(reg),
                 "--ledger", str(ledger), "--board", str(board)],
                capture_output=True, text=True)
            self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
            self.assertIn("[BLOCK]", p.stderr)
            self.assertIn("生命周期", p.stderr)
            # 冻结态下 verify 仍可用（只读）
            self.assertEqual(run_verify(tmp, ledger, reg, board).returncode, 0)

    def test_state_changes_keep_board_synced_and_history_untouched(self):
        with demo_copy() as (tmp, ledger, reg, board):
            proj = tmp / "examples" / "demo-shop"
            before = json.loads(ledger.read_text())
            events_before = before["history"]["events"]
            self.assertEqual(cli(proj, "retire", "--code", "DEMO.CORE.ORDER.01",
                                 "--reason", "取代").returncode, 0)
            after = json.loads(ledger.read_text())
            self.assertEqual(after["history"]["events"], events_before)
            self.assertEqual(run_verify(tmp, ledger, reg, board).returncode, 0)
            payload = json.loads(run_verify(tmp, ledger, reg, board).stdout)
            checks = {c["id"]: c["ok"] for c in payload["checks"]}
            self.assertTrue(checks["board_embed_synced"])
            self.assertTrue(checks["history_current_matches"])

    def test_cli_rejects_unfreeze_without_approval(self):
        with demo_copy() as (tmp, ledger, reg, board):
            proj = tmp / "examples" / "demo-shop"
            self.assertEqual(cli(proj, "freeze", "--reason", "x").returncode, 0)
            p = cli(proj, "unfreeze")
            self.assertEqual(p.returncode, 1)
            self.assertIn("approved-by", p.stderr)
            self.assertEqual(cli(proj, "unfreeze", "--approved-by", "张三").returncode, 0)

    def test_status_cli_json(self):
        with demo_copy() as (tmp, ledger, reg, board):
            proj = tmp / "examples" / "demo-shop"
            p = subprocess.run([sys.executable, str(LC), "--target", str(proj),
                                "--json", "status"], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            d = json.loads(p.stdout)
            self.assertEqual(d["state"], "active")
            self.assertTrue(d["writable"])


if __name__ == "__main__":
    unittest.main()
