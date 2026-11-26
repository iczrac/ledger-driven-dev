"""看板缺失的三态语义：显式指定却不存在 = fail，没有可用看板 = na。

回归背景
--------
旧实现只有一条分支：`add("board_embed_synced", True, "未提供看板，跳过")`。
ok=True ⇒ status=pass，于是两种**完全不同**的情况都被记成了「通过」：

  1. 没有看板的老项目（合法未启用）—— 本应是 na；
  2. 显式指定了看板路径却找不到（配置错误）—— 本应是 fail。

第 2 种就是「假绿」：门禁传错看板路径时照样报绿，并且掩盖了看板改名
引入的一处真实回归。本文件证明三态语义各归各位：

  - 显式指定却不存在的看板 → fail（--strict 退出码 1）；
  - 未提供看板且默认也解析不到 → na（既不计入 pass 也不计入 fail）；
  - 看板存在 → 照常校验 EMBED（pass），主仓自校验不因语义拆分而失去覆盖。
"""
from __future__ import annotations
MODULE_ID = "core"

import json
import subprocess
import sys
import unittest
from pathlib import Path

from _base import ROOT, VERIFIER, demo_copy


def run_verify(root: Path, ledger: Path, reg: Path, *args: str) -> subprocess.CompletedProcess:
    """不传 --board 即「未提供看板」；传了就用调用方给的路径。"""
    cmd = [sys.executable, str(VERIFIER), "--root", str(root),
           "--registry", str(reg), "--ledger", str(ledger), "--json"]
    cmd.extend(args)
    return subprocess.run(cmd, capture_output=True, text=True)


def board_row(payload: dict) -> dict:
    return next(c for c in payload["checks"] if c["id"] == "board_embed_synced")


def drop_boards(root: Path) -> None:
    for html in (root / "examples" / "demo-shop" / "governance").glob("*.html"):
        html.unlink()


class BoardTristateTest(unittest.TestCase):

    def test_explicit_missing_board_is_fail(self):
        """C6 核心：显式指定却不存在的看板 → fail，假绿被拆掉。"""
        with demo_copy() as (root, ledger, reg, board):
            missing = board.with_name("NOPE.html")
            payload = json.loads(run_verify(root, ledger, reg, "--board", str(missing)).stdout)
            row = board_row(payload)
            self.assertEqual(row["status"], "fail", row)
            self.assertFalse(row["ok"])
            self.assertFalse(payload["all_ok"])
            self.assertEqual(payload["failed"], 1)

    def test_explicit_missing_board_makes_strict_exit_nonzero(self):
        """假绿的另一半：门禁退出码必须红，不能只报一行文案。"""
        with demo_copy() as (root, ledger, reg, board):
            missing = board.with_name("NOPE.html")
            p = run_verify(root, ledger, reg, "--board", str(missing), "--strict")
            self.assertEqual(p.returncode, 1, p.stdout + p.stderr)

    def test_no_board_available_is_na(self):
        """没有可用看板且未提供 --board → na（合法未启用，老项目不被批量阻断）。"""
        with demo_copy() as (root, ledger, reg, board):
            drop_boards(root)
            payload = json.loads(run_verify(root, ledger, reg).stdout)
            row = board_row(payload)
            self.assertEqual(row["status"], "na", row)
            self.assertFalse(row["ok"])

    def test_na_counts_neither_pass_nor_fail(self):
        """三态语义：na 既不计入 passed 也不计入 failed。"""
        with demo_copy() as (root, ledger, reg, board):
            drop_boards(root)
            payload = json.loads(run_verify(root, ledger, reg).stdout)
            self.assertEqual(payload["passed"],
                             sum(1 for c in payload["checks"] if c["status"] == "pass"))
            self.assertEqual(payload["failed"],
                             sum(1 for c in payload["checks"] if c["status"] == "fail"))
            self.assertEqual(payload["na"],
                             sum(1 for c in payload["checks"] if c["status"] == "na"))
            self.assertEqual(payload["passed"] + payload["failed"] + payload["na"],
                             len(payload["checks"]))

    def test_existing_board_still_passes(self):
        """正常路径不受影响：看板存在 → 照常校验 EMBED。"""
        with demo_copy() as (root, ledger, reg, board):
            payload = json.loads(run_verify(root, ledger, reg, "--board", str(board)).stdout)
            row = board_row(payload)
            self.assertEqual(row["status"], "pass", row)
            self.assertTrue(row["ok"])
            self.assertEqual(payload["failed"], 0)

    def test_default_resolved_board_is_still_checked(self):
        """未提供 --board 但默认能解析到看板时，照样校验（主仓自校验不能失去看板覆盖）。"""
        payload = json.loads(run_verify(
            ROOT, ROOT / "governance" / "DECISION_LEDGER.json",
            ROOT / "governance" / "registry.json").stdout)
        row = board_row(payload)
        self.assertEqual(row["status"], "pass", row)
        self.assertEqual(payload["failed"], 0)


if __name__ == "__main__":
    unittest.main()
