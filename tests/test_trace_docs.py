"""规范化文档重建与编码索引：单一事实源 → 可对齐 artifact。"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from _base import ROOT, demo_copy

REBUILD = ROOT / "scripts" / "rebuild_docs.py"
INDEX = ROOT / "scripts" / "code_index.py"


def run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *map(str, args)],
                          capture_output=True, text=True)


class TraceDocsTest(unittest.TestCase):
    def test_rebuild_docs_creates_canonical_set(self):
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            out = proj / "docs" / "generated"
            self.assertFalse(out.exists())
            proc = run(REBUILD, "--target", proj)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            for name in ("PROJECT_BRIEF.md", "MODULE_MAP.md", "CAPABILITY_INDEX.md"):
                self.assertTrue((out / name).exists(), name)
            index_text = (out / "CAPABILITY_INDEX.md").read_text()
            self.assertIn("DEMO.DATA.READY.01", index_text)
            self.assertIn("L5/verified", index_text)
            self.assertNotIn(str(proj), index_text)
            self.assertNotIn("/Users/", index_text)

    def test_rebuild_docs_is_non_destructive_and_forceable(self):
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            out = proj / "docs" / "generated"
            self.assertEqual(run(REBUILD, "--target", proj).returncode, 0)
            marker = out / "PROJECT_BRIEF.md"
            marker.write_text("人工补充内容")
            again = run(REBUILD, "--target", proj)
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertEqual(marker.read_text(), "人工补充内容")
            forced = run(REBUILD, "--target", proj, "--force")
            self.assertEqual(forced.returncode, 0, forced.stderr)
            self.assertIn("PROJECT_BRIEF · DEMO", marker.read_text())

    def test_rebuild_docs_dry_run_writes_nothing(self):
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            proc = run(REBUILD, "--target", proj, "--dry-run")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse((proj / "docs" / "generated").exists())
            self.assertIn("PROJECT_BRIEF · DEMO", proc.stdout)

    def test_rebuild_docs_json_summary(self):
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            proc = run(REBUILD, "--target", proj, "--json")
            data = json.loads(proc.stdout)
            self.assertEqual(data["schema"], "doc-rebuild/1")
            self.assertEqual(data["capabilities"], 4)
            self.assertEqual(set(data["files"]),
                             {"PROJECT_BRIEF.md", "MODULE_MAP.md", "CAPABILITY_INDEX.md"})

    def test_code_index_maps_all_artifacts(self):
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            proc = run(INDEX, "--target", proj, "--json")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout)
            self.assertEqual(data["schema"], "code-index/1")
            self.assertEqual(data["summary"]["capabilities"], 4)
            by_code = {c["code"]: c for c in data["caps"]}
            cap = by_code["DEMO.CORE.PRICE.02"]
            self.assertEqual(cap["level"], 5)
            self.assertEqual(cap["tier"], "verified")
            self.assertTrue(cap["artifacts"]["tests"])
            self.assertTrue(cap["artifacts"]["docs"])
            self.assertIn(2, cap["event_seqs"])
            self.assertNotIn(str(proj), proc.stdout)

    def test_code_index_consumes_git_trace(self):
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            trace = proj / "governance" / "GIT_TRACE.json"
            trace.write_text(json.dumps({"schema": "git-trace/1", "commits": [
                {"hash": "abc1234", "subject": "price test",
                 "cap_codes": ["DEMO.CORE.PRICE.02"], "entry_ids": [], "event_seqs": [2]},
            ]}))
            proc = run(INDEX, "--target", proj, "--git-trace", trace, "--json")
            data = json.loads(proc.stdout)
            cap = next(c for c in data["caps"] if c["code"] == "DEMO.CORE.PRICE.02")
            self.assertEqual(cap["commits"], ["abc1234"])
            self.assertEqual(data["summary"]["with_commits"], 1)

    def test_code_index_non_destructive(self):
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            out = proj / "governance" / "CODE_INDEX.json"
            out.write_text("人工占位")
            proc = run(INDEX, "--target", proj)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(out.read_text(), "人工占位")
            forced = run(INDEX, "--target", proj, "--force")
            self.assertEqual(forced.returncode, 0, forced.stderr)
            self.assertEqual(json.loads(out.read_text())["schema"], "code-index/1")


if __name__ == "__main__":
    unittest.main()
