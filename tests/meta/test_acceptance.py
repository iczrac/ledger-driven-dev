"""S2 验收契约专项：证明检测器本身有效，而不是证明当前仓库已修好。

纪律：本文件全部是**绿灯**自测（喂正确/错误输入验证判定逻辑），
不断言当前仓库是红灯还是绿灯——S3 转绿后这些用例必须仍然通过。
"""
from __future__ import annotations
MODULE_ID = "meta"

import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from _base import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from acceptance import (AXIS_KEYS, TOKEN, build, check_derived, classify,  # noqa: E402
                        constants, evaluate_probe, historical, scan_literals, to_int)

EXPECT = {"axis": 7, "pre_steps": 1, "post_steps": 19,
          "verify_checks": 12, "gate_criteria": 9}


def source_version() -> str:
    """独立从权威源读版本号：发版时测试不需要手工同步字面量。"""
    m = re.search(r'^METHOD_VERSION\s*=\s*"([^"]+)"',
                  (ROOT / "scripts" / "upgrade.py").read_text(encoding="utf-8"),
                  re.M)
    assert m, "夹具失效：upgrade.py 里找不到 METHOD_VERSION"
    return m.group(1)


def hits(line: str) -> list[tuple[str, int]]:
    return [x for x in (classify(line, m) for m in TOKEN.finditer(line)) if x]


class ConstantsTest(unittest.TestCase):

    def test_expected_values_come_from_upgrade_ast(self):
        c = constants(ROOT)
        self.assertEqual(c["expect"], EXPECT)
        self.assertEqual(c["basis_errors"], [])
        self.assertEqual(c["version"], source_version())
        self.assertEqual(len(c["verify_ids"]), 12)
        self.assertEqual(len(c["gate_ids"]), 9)
        self.assertEqual(len(AXIS_KEYS), 7)
        src = (ROOT / "scripts" / "upgrade.py").read_text(encoding="utf-8")
        for key in AXIS_KEYS:
            self.assertIn(key, src, f"轴 {key} 必须被 upgrade.py 真实消费")

    def test_constants_follow_source_not_hardcoded(self):
        """改源码常量 → 期望值跟着变，证明没有把 19/12/9 写死在检测器里。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "scripts").mkdir()
            src = (ROOT / "scripts" / "upgrade.py").read_text(encoding="utf-8")
            mutated = src.replace(f'METHOD_VERSION = "{source_version()}"',
                                  'METHOD_VERSION = "9.9.9"')
            self.assertIn('METHOD_VERSION = "9.9.9"', mutated,
                          "夹具失效：源码版本字面量替换未命中")
            (root / "scripts" / "upgrade.py").write_text(
                mutated.replace('    "python3 scripts/ledger_feedback.py export --target P "\n'
                            '    "--out feedback/observations.jsonl --phase after-upgrade '
                            '--apply --approved-by <人>",\n]',
                            '    "python3 scripts/ledger_feedback.py export --target P "\n'
                            '    "--out feedback/observations.jsonl --phase after-upgrade '
                            '--apply --approved-by <人>",\n'
                            '    "python3 scripts/agent_gateway.py --target P status --json",\n]'),
                encoding="utf-8")
            c = constants(root)
            self.assertEqual(c["version"], "9.9.9")
            # POST_UPGRADE 末尾追加一步后应为 20；若源码替换未命中则说明夹具失效
            self.assertEqual(c["expect"]["post_steps"], 20)

    def test_chinese_and_arabic_numerals(self):
        self.assertEqual(to_int("六"), 6)
        self.assertEqual(to_int("18"), 18)
        self.assertEqual(to_int("十一"), 11)
        self.assertEqual(to_int("十九"), 19)
        self.assertIsNone(to_int("这一步"))
        self.assertIsNone(to_int(""))


class LiteralScanTest(unittest.TestCase):

    def _mini(self, root: Path, text: str) -> None:
        docs = root / "docs"
        if not docs.exists():
            docs.mkdir()
        (docs / "01-test.md").write_text(text, encoding="utf-8")

    def test_clean_tree_has_no_drift(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._mini(root,
                       "版本七轴（缺一不可）\n"
                       "必须跑完 19 步 post_upgrade 升级后 SOP\n"
                       "upgrade-verify/1 有 12 项 checks\n"
                       "九项关键检查全 pass\n")
            r = scan_literals(root, EXPECT)
            self.assertEqual(r["drift_count"], 0, r["drifts"])

    def test_stale_literals_are_all_named(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._mini(root,
                       "版本六轴（缺一不可）\n"
                       "必须跑完 18 步 post_upgrade 升级后 SOP\n"
                       "upgrade-verify/1 有 11 项 checks\n"
                       "八项关键检查全 pass\n")
            r = scan_literals(root, EXPECT)
            self.assertEqual(r["drift_count"], 4, r["drifts"])
            self.assertEqual({x["kind"] for x in r["drifts"]},
                             {"axis", "post_steps", "verify_checks", "gate_criteria"})
            self.assertTrue(all(x["expected"] == EXPECT[x["kind"]] for x in r["drifts"]))

    def test_historical_statements_are_review_not_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._mini(root,
                       "`upgrade.py` 从版本五轴扩到**六轴**（新增 `installed_assets`）\n"
                       "迁移 M1–M6 → **M1–M8**，`post_upgrade` 11 → **18 步**，verify 9 → **11 项**\n"
                       "| U1 | 版本三轴（v1.1.0 起五轴，v1.2.0 起六轴）+ post_upgrade 8 步（现 18 步） |\n")
            r = scan_literals(root, EXPECT)
            self.assertEqual(r["drift_count"], 0, r["drifts"])
            self.assertGreaterEqual(r["review_count"], 4)
            # 同一棵树里加一句无版本限定的当前陈述，必须重新变成硬失败
            self._mini(root,
                       (root / "docs" / "01-test.md").read_text(encoding="utf-8")
                       + "\n必须跑完 18 步升级后 SOP\n")
            r2 = scan_literals(root, EXPECT)
            self.assertEqual(r2["drift_count"], 1, r2["drifts"])
            self.assertEqual(r2["drifts"][0]["kind"], "post_steps")

    def test_unrelated_units_do_not_false_positive(self):
        """回归：这一步 / 十轴 / scenario-preflight 14 项 / 1 步基线都不是漂移。"""
        lines = [
            "**这一步已机器化**：生成器每次重跑都会写入 next_queue",
            "60 场景、十轴与已知缺漏",
            "输出 `scenario-preflight/1`（14 项检查、allowed_actions）",
            "`scenario-preflight/1`：facts、14 项 checks（pass/warn/block）",
            "1 步升级前基线与 19 步升级后 SOP",
            "第 12–18 步是 v1.2.0 新增的七步",
        ]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._mini(root, "\n".join(lines))
            r = scan_literals(root, EXPECT)
            self.assertEqual(r["drifts"], [])

    def test_historical_helper_is_conservative(self):
        self.assertTrue(historical("从版本五轴扩到六轴"))
        self.assertTrue(historical("post_upgrade 11 → **18 步**"))
        self.assertTrue(historical("第 12–18 步是 v1.2.0 新增的七步"))
        self.assertFalse(historical("→ verify 11 项 → post_upgrade 18 步 → 交回路由"))
        self.assertFalse(historical("必须跑完 18 步升级后 SOP"))

    def test_classify_names_each_kind(self):
        self.assertIn(("axis", 6), hits("版本六轴（缺一不可）"))
        self.assertIn(("post_steps", 18), hits("按 post_upgrade 的 18 步重新取证"))
        self.assertIn(("verify_checks", 11), hits("11 项 checks"))
        self.assertIn(("gate_criteria", 8), hits("八项全 pass"))


class DerivedTest(unittest.TestCase):

    def test_real_derived_files_are_reproducible(self):
        with tempfile.TemporaryDirectory() as td:
            items = check_derived(ROOT, Path(td))
            self.assertEqual(len(items), 3)
            self.assertTrue(all(x["reproducible"] for x in items), items)

    def test_hand_edited_derived_file_is_caught(self):
        """负向：手改派生文件绕过 L1 时，L2 必须报 stale。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "repo"
            root.mkdir()
            for rel in ("scripts", "tests", "docs"):
                shutil.copytree(ROOT / rel, root / rel,
                                ignore=shutil.ignore_patterns("__pycache__"))
            target = root / "docs" / "generated" / "TEST_MODULES.md"
            target.write_text(target.read_text(encoding="utf-8") + "\n手改一行\n",
                              encoding="utf-8")
            out = Path(td) / "out"
            out.mkdir()
            items = check_derived(root, out)
            stale = [x["path"] for x in items if not x["reproducible"]]
            self.assertIn("docs/generated/TEST_MODULES.md", stale, items)


class AppendOnlyTest(unittest.TestCase):

    def _rows(self) -> tuple[list[dict], list[dict]]:
        closed = {"obs_id": "OBS-closed", "status": "closed",
                  "disposition": "regression", "artifact_ref": "tests/meta/test_ontology.py",
                  "reason": "已由负向回归覆盖", "approved_by": "张三"}
        opened = {"obs_id": "OBS-open", "status": "open"}
        before = [closed, opened]
        fresh = {"obs_id": "OBS-new", "status": "open"}
        return before, [closed, opened, fresh]

    def test_correct_merge_passes(self):
        before, after = self._rows()
        r = evaluate_probe(before, after, after)
        self.assertEqual(r["status"], "pass", r["errors"])
        self.assertEqual(r["closed_before"], 1)
        self.assertEqual(r["rows_after"], 3)

    def test_overwrite_is_rejected_with_named_reasons(self):
        before, after = self._rows()
        r = evaluate_probe(before, [after[-1]], [after[-1]])
        self.assertEqual(r["status"], "fail")
        text = " ".join(r["errors"])
        self.assertIn("append-only 违例", text)
        self.assertIn("已收敛 triage 证据被销毁", text)

    def test_closed_fields_must_survive(self):
        before, after = self._rows()
        after[0] = dict(after[0], reason="被改写")
        self.assertIn("reason 被改写", " ".join(evaluate_probe(before, after, after)["errors"]))

    def test_duplicate_ids_and_non_idempotent_second_run_fail(self):
        before, after = self._rows()
        dup = after + [dict(after[-1])]
        r = evaluate_probe(before, dup, dup)
        self.assertIn("obs_id 重复", " ".join(r["errors"]))
        r2 = evaluate_probe(before, after, after + [{"obs_id": "OBS-late"}])
        self.assertIn("不幂等", " ".join(r2["errors"]))


class BuildTest(unittest.TestCase):

    def test_schema_is_stable_and_deterministic(self):
        a = build(ROOT)
        b = build(ROOT)
        self.assertEqual(a["schema"], "acceptance/1")
        self.assertEqual(a["constants"], EXPECT)
        self.assertEqual([c["id"] for c in a["checks"]],
                         ["literal_drift", "derived_reproducible", "append_only"])
        # 不写死 overall：S3 转绿后本用例仍须通过。
        self.assertEqual(json.dumps(a, ensure_ascii=False, sort_keys=True),
                         json.dumps(b, ensure_ascii=False, sort_keys=True),
                         "验收报告必须确定性、无时间戳")


if __name__ == "__main__":
    unittest.main()
