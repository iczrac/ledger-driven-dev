"""C 项：规划图缺失/为空时必须显式声明，禁止把 4 个能力误报成 actual_only 违规。

MODULE_ID = "traceability"
"""
MODULE_ID = "traceability"
import json
import subprocess
import sys
import unittest
from pathlib import Path

from _base import ROOT, demo_copy

COMPARE = ROOT / "scripts" / "compare_graphs.py"
ARCHITECT = ROOT / "scripts" / "architect_from_docs.py"
REBUILD = ROOT / "scripts" / "rebuild_docs.py"


def run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *map(str, args)],
                          capture_output=True, text=True)


class PlanStatusTest(unittest.TestCase):
    def test_absent_plan_is_distinguishable_from_present(self):
        """无 TARGET_ARCHITECTURE 时 plan_status=absent，且不得报 4 处违规。"""
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            proc = run(COMPARE, "--target", proj, "--json")
            data = json.loads(proc.stdout)
            self.assertEqual(data["plan_status"], "absent")
            self.assertEqual(data["summary"]["actual_only"], 0)
            self.assertEqual(data["sources"]["plan"], "registry.json (fallback)")

    def test_empty_plan_is_flagged_not_treated_as_valid(self):
        """architect 生成空图（confidence=low）时 plan_status=empty，警告不可采信。"""
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            run(REBUILD, "--target", proj)
            run(ARCHITECT, "--target", proj)
            arch = proj / "governance" / "TARGET_ARCHITECTURE.json"
            data = json.loads(arch.read_text())
            data["capabilities"] = []
            data["modules"] = []
            data["confidence"] = "low"
            arch.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            proc = run(COMPARE, "--target", proj, "--force", "--json")
            diff = json.loads(proc.stdout)
            self.assertEqual(diff["plan_status"], "empty")
            self.assertTrue(any("不可采信" in w or "缺失" in w for w in diff["warnings"]))
            self.assertEqual(diff["summary"]["actual_only"], 4)

    def test_report_first_line_states_plan_unusable(self):
        """GRAPH_DIFF.md 首行必须说清规划图缺失、漂移结论不可采信。"""
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            run(REBUILD, "--target", proj)
            run(ARCHITECT, "--target", proj)
            arch = proj / "governance" / "TARGET_ARCHITECTURE.json"
            data = json.loads(arch.read_text())
            data["capabilities"] = []
            data["confidence"] = "low"
            arch.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            run(COMPARE, "--target", proj, "--force")
            report = (proj / "docs" / "generated" / "GRAPH_DIFF.md").read_text()
            self.assertIn("不可采信", report.splitlines()[0])

    def test_empty_plan_does_not_dispatch_archaeologist(self):
        """无有效规划时不得派 project-archaeologist 校准规划图，应指向 architect_from_docs。"""
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            run(REBUILD, "--target", proj)
            run(ARCHITECT, "--target", proj)
            arch = proj / "governance" / "TARGET_ARCHITECTURE.json"
            data = json.loads(arch.read_text())
            data["capabilities"] = []
            arch.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            proc = run(COMPARE, "--target", proj, "--force", "--json")
            diff = json.loads(proc.stdout)
            experts = {e["expert"] for e in diff["execution_order"]}
            self.assertNotIn("project-archaeologist", experts)
            self.assertTrue(any("architect_from_docs" in e["action"]
                                for e in diff["execution_order"]))

    def test_partial_plan_status(self):
        """有模块无能力判 partial，同样禁用漂移结论。"""
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            run(REBUILD, "--target", proj)
            run(ARCHITECT, "--target", proj)
            arch = proj / "governance" / "TARGET_ARCHITECTURE.json"
            data = json.loads(arch.read_text())
            data["capabilities"] = []
            arch.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            proc = run(COMPARE, "--target", proj, "--force", "--json")
            diff = json.loads(proc.stdout)
            self.assertIn(diff["plan_status"], ("empty", "partial"))

    def test_present_plan_status_unchanged(self):
        """正常规划图 plan_status=present，既有输出形状不变。"""
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            run(REBUILD, "--target", proj)
            run(ARCHITECT, "--target", proj)
            proc = run(COMPARE, "--target", proj, "--force", "--json")
            diff = json.loads(proc.stdout)
            self.assertEqual(diff["plan_status"], "present")
            self.assertEqual(diff["summary"]["actual_only"], 0)


if __name__ == "__main__":
    unittest.main()
