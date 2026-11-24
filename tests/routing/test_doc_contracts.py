"""六份专家契约的文档职责与权限互斥：不得出现两个专家都能写同一份文档。"""
MODULE_ID = "routing"
import re
import unittest
from pathlib import Path

from _base import ROOT

EXPERTS = ROOT / "experts"
TARGETS = ["ledger-steward", "evidence-auditor", "project-archaeologist",
           "release-steward", "loop-executor", "goal-orchestrator"]


def read_contract(name: str) -> str:
    return (EXPERTS / name / "EXPERT.md").read_text(encoding="utf-8")


class DocContractTest(unittest.TestCase):
    def test_each_contract_has_five_sections(self):
        for name in TARGETS:
            text = read_contract(name)
            for anchor in ("职责边界", "权限", "禁止", "停止", "交接"):
                self.assertIn(anchor, text, f"{name} 缺 {anchor}")

    def test_each_contract_mentions_doc_lifecycle(self):
        for name in TARGETS:
            text = read_contract(name)
            self.assertTrue(re.search(r"文档|文檔|docs\.registry|doc-lifecycle", text),
                            f"{name} 未写文档职责")

    def test_only_one_expert_writes_docs_registry(self):
        # 表格「写」列中声明写 docs.registry 的只有 ledger-steward。
        writers = []
        for name in TARGETS:
            text = read_contract(name)
            for line in text.splitlines():
                if not line.strip().startswith("|"):
                    continue
                if "docs.registry" not in line and "docs.obligations" not in line:
                    continue
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                action = cells[0]
                if not (action.startswith("写") or action.startswith("写 ")):
                    continue
                if "**禁止**" in cells[1]:
                    continue
                writers.append(name)
        self.assertEqual(set(writers), {"ledger-steward"},
                         f"docs.registry 写入方不唯一：{writers}")

    def test_evidence_auditor_never_writes_docs(self):
        text = read_contract("evidence-auditor")
        self.assertIn("不得写文档", text)
        self.assertIn("不得关闭", text)

    def test_release_steward_gate_blocks_stale(self):
        text = read_contract("release-steward")
        self.assertIn("stale", text)
        self.assertIn("发布门", text)

    def test_loop_executor_accepts_doc_card(self):
        text = read_contract("loop-executor")
        self.assertIn("kind=doc", text)
        self.assertIn("一次只做一张", text)

    def test_goal_orchestrator_counts_doc_progress(self):
        text = read_contract("goal-orchestrator")
        self.assertIn("文档覆盖率", text)
        self.assertIn("stall", text)
