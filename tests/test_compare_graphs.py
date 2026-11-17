"""规划图 vs 实际图：能力级 diff、缺口与专家执行顺序。"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from _base import ROOT, demo_copy

REBUILD = ROOT / "scripts" / "rebuild_docs.py"
ARCHITECT = ROOT / "scripts" / "architect_from_docs.py"
COMPARE = ROOT / "scripts" / "compare_graphs.py"


def run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *map(str, args)],
                          capture_output=True, text=True)


def prepare(proj: Path) -> None:
    assert run(REBUILD, "--target", proj).returncode == 0
    assert run(ARCHITECT, "--target", proj).returncode == 0


class CompareGraphsTest(unittest.TestCase):
    def test_compare_planned_and_actual(self):
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            prepare(proj)
            proc = run(COMPARE, "--target", proj, "--json")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout)
            self.assertEqual(data["schema"], "graph-diff/1")
            self.assertEqual(data["summary"]["planned"], 4)
            self.assertEqual(data["summary"]["actual"], 4)
            self.assertEqual(data["summary"]["aligned"], 3)
            self.assertEqual(data["summary"]["in_progress"], 1)
            self.assertEqual(data["summary"]["planned_only"], 0)
            self.assertEqual(data["summary"]["actual_only"], 0)
            api = next(r for r in data["comparison"] if r["code"] == "DEMO.API.QUERY.01")
            self.assertEqual(api["level"], "L2")
            self.assertTrue(api["gaps"])
            self.assertNotIn(str(proj), proc.stdout)

    def test_execution_order_uses_next_queue_and_experts(self):
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            prepare(proj)
            proc = run(COMPARE, "--target", proj, "--json")
            data = json.loads(proc.stdout)
            first = data["execution_order"][0]
            self.assertEqual(first["code"], "DEMO.API.QUERY.01")
            self.assertEqual(first["expert"], "loop-executor")
            self.assertIn("evidence-auditor", "；".join(first["preconditions"]))
            self.assertEqual(first["lessons"], ["L-001"])
            self.assertIn(data["overall_expert"],
                          {"ledger-steward", "evidence-auditor", "loop-executor"})

    def test_planned_only_capability_gets_archaeologist(self):
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            prepare(proj)
            arch = proj / "governance" / "TARGET_ARCHITECTURE.json"
            data = json.loads(arch.read_text())
            data["capabilities"].append({
                "code": "DEMO.NEW.TASK.01", "name": "新任务", "target_level": "L3",
                "depends_on": [], "sources": ["docs/plans/NEW_PLAN.md"],
            })
            arch.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            proc = run(COMPARE, "--target", proj, "--force", "--json")
            diff = json.loads(proc.stdout)
            new = next(r for r in diff["comparison"] if r["code"] == "DEMO.NEW.TASK.01")
            self.assertEqual(new["status"], "planned_only")
            self.assertEqual(new["target_level"], "L3")
            ordered = next(e for e in diff["execution_order"] if e["code"] == "DEMO.NEW.TASK.01")
            self.assertEqual(ordered["expert"], "project-archaeologist")

    def test_actual_only_capability_gets_steward(self):
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            prepare(proj)
            arch = proj / "governance" / "TARGET_ARCHITECTURE.json"
            data = json.loads(arch.read_text())
            data["capabilities"] = [c for c in data["capabilities"]
                                    if c["code"] == "DEMO.DATA.READY.01"]
            arch.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            proc = run(COMPARE, "--target", proj, "--force", "--json")
            diff = json.loads(proc.stdout)
            self.assertEqual(diff["summary"]["actual_only"], 3)
            ordered = next(e for e in diff["execution_order"] if e["code"] == "DEMO.CORE.ORDER.01")
            self.assertEqual(ordered["expert"], "ledger-steward")

    def test_outputs_are_non_destructive_and_forceable(self):
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            prepare(proj)
            out = proj / "governance" / "GRAPH_DIFF.json"
            rep = proj / "docs" / "generated" / "GRAPH_DIFF.md"
            out.write_text("人工记录")
            rep.write_text("人工报告")
            proc = run(COMPARE, "--target", proj)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(out.read_text(), "人工记录")
            self.assertEqual(rep.read_text(), "人工报告")
            forced = run(COMPARE, "--target", proj, "--force")
            self.assertEqual(forced.returncode, 0, forced.stderr)
            self.assertEqual(json.loads(out.read_text())["schema"], "graph-diff/1")
            self.assertIn("规划图 vs 实际图", rep.read_text())

    def test_fallback_to_registry_warns(self):
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            proc = run(COMPARE, "--target", proj, "--json")
            data = json.loads(proc.stdout)
            self.assertEqual(data["sources"]["plan"], "registry.json (fallback)")
            self.assertTrue(any("architect_from_docs" in w for w in data["warnings"]))
            self.assertEqual(data["summary"]["planned"], 4)


if __name__ == "__main__":
    unittest.main()
