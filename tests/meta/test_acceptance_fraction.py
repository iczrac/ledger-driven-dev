"""「N/N」形式的数字漂移检测：总数陈述不再是盲区。

回归背景
--------
字面量漂移检测器（L1 literal_drift）的词表原先只认「N 轴 / 步 / 项 / 条」，
于是「`verify --strict`，18/18」这类**总数陈述完全隐形**：分母写错了也没人
发现。同类数字漂移已经漏检过一次（2026-11-23），所以这里补上「N/N」形式的
识别，并同时锁住**不误伤**的边界——覆盖率、单测数、规模预算、序号都不是
不变量总数，不能被当成漂移。

纪律：本文件全部是绿灯自测（喂对/错输入验证判定逻辑），不断言当前仓库
是红是绿——仓库修好后这些用例仍必须通过。
"""
from __future__ import annotations
MODULE_ID = "meta"

import sys
import tempfile
import unittest
from pathlib import Path

from _base import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from acceptance import (FRACTION_TOKEN, classify_fraction,  # noqa: E402
                        scan_literals)

EXPECT = {"axis": 7, "pre_steps": 1, "post_steps": 19,
          "verify_checks": 12, "gate_criteria": 9, "invariants": 32}


def fraction_hits(line: str) -> list[tuple[str, int]]:
    return [x for x in (classify_fraction(line, m)
                        for m in FRACTION_TOKEN.finditer(line)) if x]


class FractionDriftTest(unittest.TestCase):

    def _scan(self, *files: tuple[str, str]) -> dict:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for rel, text in files:
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            return scan_literals(root, EXPECT)

    def test_fraction_token_matches_pass_over_total(self):
        """词表认得「N/N」了（原先只认「N 轴/步/项/条」）。"""
        self.assertTrue(FRACTION_TOKEN.search("`verify --strict`，18/18"))
        self.assertTrue(FRACTION_TOKEN.search("32/32 条不变量"))

    def test_stale_fraction_total_is_caught(self):
        """核心负向：总数漂移必须被点名，而不是隐形通过。"""
        r = self._scan(("docs/01-test.md",
                        "2. **账本**：`verify --strict`，18/18；\n"))
        self.assertEqual(r["drift_count"], 1, r["drifts"])
        d = r["drifts"][0]
        self.assertEqual(d["kind"], "invariants")
        self.assertEqual(d["actual"], 18)
        self.assertEqual(d["expected"], EXPECT["invariants"])

    def test_stale_fraction_named_by_invariant_context(self):
        """「不变量：N/N」同样被点名。"""
        r = self._scan(("docs/01-test.md", "不变量：21/21 或失败清单\n"))
        self.assertEqual(r["drift_count"], 1, r["drifts"])
        self.assertEqual(r["drifts"][0]["kind"], "invariants")
        self.assertEqual(r["drifts"][0]["actual"], 21)

    def test_correct_fraction_is_clean(self):
        """总数与权威口径一致 → 不报漂移。"""
        r = self._scan(("docs/01-test.md", "不变量：30/32 或失败清单\n"))
        self.assertEqual(r["drift_count"], 0, r["drifts"])

    def test_fractions_outside_context_are_not_flagged(self):
        """边界：覆盖率 / 单测数 / 规模预算都不是不变量总数，不能误伤。"""
        r = self._scan(("docs/01-test.md",
                        "证据分层：verified 仍 20/47，覆盖率 16/42\n"
                        "全量门禁：单测 476/476 通过\n"
                        "规模预算 50 / 100 / 50 / 3\n"))
        self.assertEqual(r["drift_count"], 0, r["drifts"])

    def test_ordinal_is_not_a_total(self):
        """「第 28/29 条」是序号不是总数（沿用「N 条」规则的同一排除）。"""
        r = self._scan(("docs/01-test.md",
                        "改数据字段 → 第 28/29 条不变量 + 对应测试\n"))
        self.assertEqual(r["drift_count"], 0, r["drifts"])

    def test_release_log_section_is_historical(self):
        """发布日志里带版本号的小节记的是「当时」的数字 → 归 review，不归漂移。"""
        r = self._scan(("RELEASE_CHECKLIST.md",
                        "## 功能完整性\n"
                        "- [x] 可信性校验器：32 条不变量\n"
                        "\n"
                        "## v2.25.1 发布检查\n"
                        "- [x] 示例：verify_ledger 24/24 通过\n"))
        self.assertEqual(r["drift_count"], 0, r["drifts"])
        self.assertTrue(any(x["path"] == "RELEASE_CHECKLIST.md"
                            for x in r["review"]))

    def test_release_log_current_section_is_still_scanned(self):
        """发布日志的「当前状态」小节仍然受检（不是整文件豁免）。"""
        r = self._scan(("RELEASE_CHECKLIST.md",
                        "## 功能完整性\n"
                        "- [x] 可信性校验器：24 条不变量\n"))
        self.assertEqual(r["drift_count"], 1, r["drifts"])
        self.assertEqual(r["drifts"][0]["kind"], "invariants")

    def test_contributing_and_release_checklist_are_in_scan_scope(self):
        """扫描范围纳入 CONTRIBUTING.md 与 RELEASE_CHECKLIST.md。"""
        r = self._scan(("CONTRIBUTING.md",
                        "账本校验（32 条三态不变量）\n"),
                       ("RELEASE_CHECKLIST.md",
                        "## 功能完整性\n"
                        "- [x] 可信性校验器：24 条不变量\n"))
        self.assertEqual(r["scanned_files"], 2)
        self.assertEqual(r["drift_count"], 1, r["drifts"])
        self.assertEqual(r["drifts"][0]["path"], "RELEASE_CHECKLIST.md")

    def test_classify_fraction_rejects_inverted_ratio(self):
        """「54 / 8」这类分子大于分母的比例不是「通过数/总数」。"""
        self.assertEqual(fraction_hits("场景矩阵 54 / 8 轴"), [])


if __name__ == "__main__":
    unittest.main()
