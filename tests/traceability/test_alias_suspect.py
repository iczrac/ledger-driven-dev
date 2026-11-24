"""D 项：同义异码 impl 路径配对——shadow 只晒不否决。

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
REBUILD = ROOT / "scripts" / "rebuild_docs.py"
ARCHITECT = ROOT / "scripts" / "architect_from_docs.py"


def run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *map(str, args)],
                          capture_output=True, text=True)


class AliasSuspectTest(unittest.TestCase):
    def _setup(self, proj: Path, planned_code: str, impl: list[str]) -> dict:
        run(REBUILD, "--target", proj)
        run(ARCHITECT, "--target", proj)
        arch = proj / "governance" / "TARGET_ARCHITECTURE.json"
        data = json.loads(arch.read_text())
        actual = next(c for c in data["capabilities"]
                      if c["code"] == "DEMO.CORE.PRICE.02")
        rename = {"code": planned_code, "name": "同义码", "target_level": "L5",
                  "depends_on": [], "sources": actual.get("sources", []),
                  "impl_hint": impl}
        data["capabilities"] = [c for c in data["capabilities"]
                                if c["code"] != actual["code"]] + [rename]
        arch.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        return json.loads((proj / "governance" / "DECISION_LEDGER.json").read_text())

    def test_same_impl_path_gets_alias_suspect_both_ways(self):
        """规划码与实际码 impl 路径相同 → 双向 alias_suspect，进入 shadow_pairs。"""
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            self._setup(proj, "DEMO.CORE.ISSUE.02", ["src/domain/pricing.py"])
            proc = run(COMPARE, "--target", proj, "--force", "--json")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            diff = json.loads(proc.stdout)
            pairs = [p for p in diff["shadow_pairs"]
                     if p.get("kind") == "alias_suspect"]
            self.assertTrue(pairs)
            self.assertTrue(any(p.get("planned") == "DEMO.CORE.ISSUE.02" for p in pairs))
            planned = next(r for r in diff["comparison"]
                           if r["code"] == "DEMO.CORE.ISSUE.02")
            actual = next(r for r in diff["comparison"]
                          if r["code"] == "DEMO.CORE.PRICE.02")
            self.assertIn("DEMO.CORE.PRICE.02", planned["alias_matches"])
            self.assertIn("DEMO.CORE.ISSUE.02", actual["alias_matches"])

    def test_alias_does_not_change_status_or_level(self):
        """硬约束：不改 status/level/不自动合并，字面判定保持。"""
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            self._setup(proj, "DEMO.CORE.ISSUE.02", ["src/domain/pricing.py"])
            proc = run(COMPARE, "--target", proj, "--force", "--json")
            diff = json.loads(proc.stdout)
            planned = next(r for r in diff["comparison"]
                           if r["code"] == "DEMO.CORE.ISSUE.02")
            actual = next(r for r in diff["comparison"]
                          if r["code"] == "DEMO.CORE.PRICE.02")
            self.assertEqual(planned["status"], "planned_only")
            self.assertEqual(actual["status"], "actual_only")
            self.assertEqual(planned["level"], "L0")
            self.assertEqual(actual["level"], "L5")

    def test_alias_warning_is_machine_and_human_visible(self):
        """alias_suspect 进 warnings 且人读报告可见。"""
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            self._setup(proj, "DEMO.CORE.ISSUE.02", ["src/domain/pricing.py"])
            run(COMPARE, "--target", proj, "--force")
            diff = json.loads((proj / "governance" / "GRAPH_DIFF.json").read_text())
            self.assertTrue(any("同义异码" in w or "alias" in w
                                for w in diff["warnings"]))
            report = (proj / "docs" / "generated" / "GRAPH_DIFF.md").read_text()
            self.assertIn("同义异码", report)

    def test_shared_impl_with_different_module_is_not_paired(self):
        """缓解误报：模块码不同则即使 impl 相同也不配对。"""
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            self._setup(proj, "DEMO.OTHER.ISSUE.02", ["src/domain/pricing.py"])
            proc = run(COMPARE, "--target", proj, "--force", "--json")
            diff = json.loads(proc.stdout)
            pairs = [p for p in diff["shadow_pairs"]
                     if p.get("kind") == "alias_suspect"]
            self.assertFalse(pairs)


if __name__ == "__main__":
    unittest.main()
