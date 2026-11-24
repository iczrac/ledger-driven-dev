"""文档→目标架构、git→决策/迭代追踪：可追溯性的两条输入链路。"""
MODULE_ID = "traceability"
import json
import subprocess
import sys
import unittest
from pathlib import Path

from _base import ROOT, demo_copy

ARCHITECT = ROOT / "scripts" / "architect_from_docs.py"
REBUILD = ROOT / "scripts" / "rebuild_docs.py"
GIT_TRACE = ROOT / "scripts" / "trace_git.py"


def run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *map(str, args)],
                          capture_output=True, text=True)


def init_git(proj: Path) -> None:
    for args in (["init", "-q"], ["config", "user.email", "test@example.com"],
                 ["config", "user.name", "Test"], ["add", "."],
                 ["commit", "-qm", "price test and order implementation"]):
        proc = subprocess.run(["git", "-C", str(proj), *args], capture_output=True, text=True)
        if proc.returncode != 0 and args[0] != "config":
            raise AssertionError(f"git {args[0]} failed: {proc.stderr}")


class TraceArchGitTest(unittest.TestCase):
    def test_docs_to_target_architecture(self):
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            self.assertEqual(run(REBUILD, "--target", proj).returncode, 0)
            proc = run(ARCHITECT, "--target", proj, "--json")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout)
            self.assertEqual(data["schema"], "target-arch/1")
            self.assertGreaterEqual(len(data["goals"]), 3)
            self.assertEqual(len(data["modules"]), 3)
            self.assertEqual(len(data["capabilities"]), 4)
            self.assertEqual(data["confidence"], "high")
            codes = {c["code"] for c in data["capabilities"]}
            self.assertIn("DEMO.CORE.PRICE.02", codes)
            self.assertTrue(any("PROJECT_BRIEF.md" in d for d in data["source_docs"]))

    def test_dependency_is_extracted_from_docs(self):
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            self.assertEqual(run(REBUILD, "--target", proj).returncode, 0)
            doc = proj / "docs" / "plans" / "DEPENDENCY.md"
            doc.parent.mkdir(parents=True, exist_ok=True)
            doc.write_text("| DEMO.CORE.ORDER.01 | L2/declared | 订单 | — | — | — | — | "
                           "依赖: DEMO.DATA.READY.01 |\n")
            proc = run(ARCHITECT, "--target", proj, "--force", "--json")
            data = json.loads(proc.stdout)
            order = next(c for c in data["capabilities"] if c["code"] == "DEMO.CORE.ORDER.01")
            self.assertIn("DEMO.DATA.READY.01", order["depends_on"])

    def test_architect_is_non_destructive(self):
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            out = proj / "governance" / "TARGET_ARCHITECTURE.json"
            out.write_text("人工规划稿")
            proc = run(ARCHITECT, "--target", proj)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(out.read_text(), "人工规划稿")
            run(ARCHITECT, "--target", proj, "--force")
            self.assertEqual(json.loads(out.read_text())["schema"], "target-arch/1")

    def test_architect_empty_docs_warns(self):
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            proc = run(ARCHITECT, "--target", proj, "--docs-dir", proj / "empty", "--json")
            data = json.loads(proc.stdout)
            # E2：规划码来自 registry 声明，空文档不再让规划图失效；警告仍显式存在。
            self.assertEqual(data["confidence"], "high")
            self.assertTrue(any("未发现文档" in w for w in data["warnings"]))
            self.assertEqual(len(data["capabilities"]), 4)

    def test_module_map_empty_caps_column_infers_codes_without_crash(self):
        """人写规划稿常把能力编码列留空；应回退到 CAPABILITY_INDEX，而不是 unpack 崩溃。"""
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            self.assertEqual(run(REBUILD, "--target", proj).returncode, 0)
            mod = proj / "docs" / "generated" / "MODULE_MAP.md"
            lines = mod.read_text(encoding="utf-8").splitlines()
            idx = next(i for i, line in enumerate(lines) if line.startswith("| CORE |"))
            lines[idx] = "| CORE | 核心 | （无） |  |"
            mod.write_text("\n".join(lines) + "\n", encoding="utf-8")

            proc = run(ARCHITECT, "--target", proj, "--force", "--json")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout)
            core = next(m for m in data["modules"] if m["code"] == "CORE")
            self.assertIn("DEMO.CORE.PRICE.02", core["caps"])

    def test_malformed_capability_code_fails_closed_with_actionable_hint(self):
        """下划线码不得被静默丢弃；必须报出文件、原码与唯一 codec 的合法写法。"""
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            self.assertEqual(run(REBUILD, "--target", proj).returncode, 0)
            mod = proj / "docs" / "generated" / "MODULE_MAP.md"
            mod.write_text(mod.read_text(encoding="utf-8")
                           .replace("DEMO.CORE.PRICE.02", "DEMO.CORE.PRICE_02.02"),
                           encoding="utf-8")

            proc = run(ARCHITECT, "--target", proj, "--force", "--json")
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            msg = proc.stderr
            self.assertIn("MODULE_MAP.md", msg)
            self.assertIn("DEMO.CORE.PRICE_02.02", msg)
            self.assertIn("DEMO.CORE.PRICE02.02", msg)
            self.assertIn("四段式", msg)

    def test_git_trace_maps_paths_to_capabilities_and_events(self):
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            init_git(proj)
            proc = run(GIT_TRACE, "--target", proj, "--json")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout)
            self.assertEqual(data["schema"], "git-trace/1")
            self.assertGreaterEqual(data["summary"]["commits"], 1)
            self.assertGreaterEqual(data["summary"]["mapped_commits"], 1)
            commit = data["commits"][0]
            self.assertIn("DEMO.CORE.ORDER.01", commit["cap_codes"])
            self.assertIn("CORE", commit["modules"])
            self.assertIn(2, commit["event_seqs"])
            self.assertNotIn(str(proj), proc.stdout)

    def test_git_trace_requires_repo_and_respects_existing(self):
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            no_repo = run(GIT_TRACE, "--target", proj)
            self.assertEqual(no_repo.returncode, 2)
            init_git(proj)
            out = proj / "governance" / "GIT_TRACE.json"
            out.write_text("人工记录")
            run(GIT_TRACE, "--target", proj)
            self.assertEqual(out.read_text(), "人工记录")
            forced = run(GIT_TRACE, "--target", proj, "--force")
            self.assertEqual(forced.returncode, 0, forced.stderr)
            self.assertEqual(json.loads(out.read_text())["schema"], "git-trace/1")


if __name__ == "__main__":
    unittest.main()
