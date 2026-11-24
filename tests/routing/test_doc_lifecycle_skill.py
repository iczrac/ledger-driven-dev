"""文档生命周期技能：骨架不可信、五项不变量、技能契约完整。"""
MODULE_ID = "routing"
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _base import ROOT

SKILLS = ROOT / "skills"
DOC_LIFECYCLE = SKILLS / "doc-lifecycle" / "SKILL.md"


def read(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


class DocLifecycleSkillTest(unittest.TestCase):
    def test_skill_exists_with_required_sections(self):
        self.assertTrue(DOC_LIFECYCLE.exists())
        text = DOC_LIFECYCLE.read_text(encoding="utf-8")
        for cmd in ("scaffold", "lint", "mark-stale", "clear-suspect", "check"):
            self.assertIn(cmd, text)
        for anchor in ("触发词", "输入", "输出", "允许动作", "禁止动作", "fail-closed", "交接"):
            self.assertIn(anchor, text)

    def test_scaffold_skeleton_never_compliant(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            s = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "doc_lifecycle.py"),
                 "scaffold", "--target", str(root), "--doc", "docs/plan/api.md",
                 "--kind", "plan", "--json"],
                capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(s.returncode, 0, s.stderr)
            out = json.loads(s.stdout)
            self.assertEqual(out["status"], "incomplete")
            self.assertIn("<!-- 待人工填写 -->", (root / "docs/plan/api.md").read_text())
            lint = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "doc_lifecycle.py"),
                 "lint", "--target", str(root), "--json"],
                capture_output=True, text=True, cwd=ROOT)
            report = json.loads(lint.stdout)
            self.assertNotIn("compliant", [d.get("status") for d in report["docs"]])
            self.assertTrue(any(d["status"] == "incomplete" for d in report["docs"]))

    def test_stale_plan_doc_fails_gate_with_path_and_reason(self):
        """计划文档 stale_after 过期 → check/lint 红且指出具体文件与原因。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "governance").mkdir()
            (root / "docs" / "plan").mkdir(parents=True)
            (root / "docs" / "plan" / "api.md").write_text(
                "# 计划：API\n\n正文\n\nstatus: draft\n", encoding="utf-8")
            ledger = {"docs": {"registry": {
                "docs/plan/api.md": {"role": "plan", "stale_after": "2020-01-01",
                                     "owner": "human"}
            }}}
            (root / "governance" / "DECISION_LEDGER.json").write_text(
                json.dumps(ledger), encoding="utf-8")
            cmd = [sys.executable, str(ROOT / "scripts" / "doc_lifecycle.py"),
                   "check", "--target", str(root), "--json"]
            s = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(s.returncode, 1, s.stdout + s.stderr)
            out = json.loads(s.stdout)
            stale = [i for i in out["issues"] if i.get("status") == "stale"]
            self.assertTrue(stale, out)
            self.assertEqual(stale[0]["path"], "docs/plan/api.md")
            self.assertIn("stale_after", stale[0]["reason"])

    def test_ledger_verify_declares_five_doc_invariants(self):
        text = read("ledger-verify")
        for inv in ("覆盖完整", "派生可复算", "信任一致", "义务已声明", "无孤儿"):
            self.assertIn(inv, text)

    def test_ledger_guard_links_doc_lint(self):
        self.assertIn("doc-lifecycle lint", read("ledger-guard"))

    def test_doc_rebuild_declares_project_state_and_check(self):
        text = read("doc-rebuild")
        self.assertIn("PROJECT_STATE", text)
        self.assertIn("--check", text)
        self.assertIn("派生文档禁止手改", text)

    def test_graph_compare_declares_rules_and_shadow(self):
        text = read("graph-compare")
        self.assertIn("可执行规则断言", text)
        self.assertIn("suspect", text)
        self.assertIn("shadow", text)
