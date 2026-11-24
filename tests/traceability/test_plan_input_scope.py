"""B 项：规划码只能来自 CAPABILITY_INDEX（账本投影），手写文档示例码不得污染规划图。

MODULE_ID = "traceability"
"""
MODULE_ID = "traceability"
import json
import subprocess
import sys
import unittest
from pathlib import Path

from _base import ROOT, demo_copy

ARCHITECT = ROOT / "scripts" / "architect_from_docs.py"
REBUILD = ROOT / "scripts" / "rebuild_docs.py"
COMPARE = ROOT / "scripts" / "compare_graphs.py"


def run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *map(str, args)],
                          capture_output=True, text=True)


class PlanInputScopeTest(unittest.TestCase):
    def test_example_code_in_prose_is_not_planned(self):
        """手写文档正文里的示例码（DEMO.*/X.Y.Z.01）不得进入规划图。"""
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            run(REBUILD, "--target", proj)
            extra = proj / "docs" / "05-讲解.md"
            extra.write_text(
                "# 讲解\n\n示例：DEMO.API.QUERY.99 与 X.Y.Z.01 仅作格式演示，"
                "目标：L5 依赖：DEMO.CORE.ORDER.01\n", encoding="utf-8")
            proc = run(ARCHITECT, "--target", proj, "--force")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            arch = json.loads((proj / "governance" / "TARGET_ARCHITECTURE.json").read_text())
            codes = {c["code"] for c in arch["capabilities"]}
            self.assertNotIn("DEMO.API.QUERY.99", codes)
            self.assertNotIn("X.Y.Z.01", codes)

    def test_capability_index_codes_are_planned(self):
        """CAPABILITY_INDEX 的码必须全部进入规划图（唯一规划输入）。"""
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            run(REBUILD, "--target", proj)
            proc = run(ARCHITECT, "--target", proj, "--force")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            arch = json.loads((proj / "governance" / "TARGET_ARCHITECTURE.json").read_text())
            codes = {c["code"] for c in arch["capabilities"]}
            self.assertTrue(codes)
            self.assertTrue(all(c.startswith("DEMO.") for c in codes))

    def test_handwritten_target_level_augments_known_code(self):
        """手写文档的 目标：Lx 只补充已知码，不改变规划码集合。"""
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            run(REBUILD, "--target", proj)
            run(ARCHITECT, "--target", proj, "--force")
            arch = proj / "governance" / "TARGET_ARCHITECTURE.json"
            data = json.loads(arch.read_text())
            target = data["capabilities"][0]["code"]
            extra = proj / "docs" / "06-规划.md"
            extra.write_text(f"# 规划\n\n- {target}：目标：L4\n", encoding="utf-8")
            run(ARCHITECT, "--target", proj, "--force")
            data = json.loads(arch.read_text())
            entry = next(c for c in data["capabilities"] if c["code"] == target)
            self.assertEqual(entry["target_level"], "L4")

    def test_handwritten_depends_on_augments_known_code(self):
        """手写文档的 依赖：CODE 只补充已知码之间的关系。"""
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            run(REBUILD, "--target", proj)
            run(ARCHITECT, "--target", proj, "--force")
            arch = proj / "governance" / "TARGET_ARCHITECTURE.json"
            data = json.loads(arch.read_text())
            child, parent = [c["code"] for c in data["capabilities"][:2]]
            extra = proj / "docs" / "07-依赖.md"
            extra.write_text(f"# 依赖\n\n- {child}：目标：L5 依赖：{parent}\n", encoding="utf-8")
            run(ARCHITECT, "--target", proj, "--force")
            data = json.loads(arch.read_text())
            entry = next(c for c in data["capabilities"] if c["code"] == child)
            self.assertIn(parent, entry["depends_on"])

    def test_pollution_rate_drops_to_zero(self):
        """端到端：手写示例码不再产出假 planned_only。"""
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            run(REBUILD, "--target", proj)
            extra = proj / "docs" / "08-示例.md"
            extra.write_text("# 示例\n\n写法如 DEMO.FAKE.DEMO.99 与 X.Y.Z.01。\n", encoding="utf-8")
            run(ARCHITECT, "--target", proj, "--force")
            proc = run(COMPARE, "--target", proj, "--force", "--json")
            diff = json.loads(proc.stdout)
            codes = {r["code"] for r in diff["comparison"]}
            self.assertNotIn("DEMO.FAKE.DEMO.99", codes)
            self.assertNotIn("X.Y.Z.01", codes)
            self.assertEqual(diff["summary"]["planned"], 4)


if __name__ == "__main__":
    unittest.main()
