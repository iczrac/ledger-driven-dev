"""文件布局清单：自检、渲染幂等、代码交叉验证与只读 diff 的负向证明。"""
from __future__ import annotations
MODULE_ID = "meta"

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _base import DEMO, ROOT, demo_copy

from file_layout import (ABS_RE, ENTRIES, LEDGER_FIELDS, NOT_IN_TARGET,
                         diff, render_md, validate)

LAYOUT = ROOT / "scripts" / "file_layout.py"
INIT = ROOT / "scripts" / "init_project.py"
DISCOVER = ROOT / "scripts" / "discover_project.py"


def cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(LAYOUT), *args],
                          capture_output=True, text=True)


def tree_hash(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            out[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


class LayoutDefinitionTest(unittest.TestCase):

    def test_definition_passes_selfcheck(self):
        self.assertEqual(validate(), [])

    def test_cli_check_and_json(self):
        p = cli("--check")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("布局定义自检通过", p.stdout)
        d = json.loads(cli("--json").stdout)
        self.assertEqual(d["schema"], "file-layout/1")
        self.assertEqual(d["total"], len(ENTRIES))
        self.assertIn("governance/registry.json", d["required"])
        self.assertGreater(d["ledger_fields"], 0)

    def test_no_absolute_paths_in_definition(self):
        for e in ENTRIES:
            blob = json.dumps(e, ensure_ascii=False)
            self.assertIsNone(ABS_RE.search(blob), f"绝对路径泄露：{e['path']}")
        self.assertIsNone(ABS_RE.search(render_md()))

    def test_check_catches_producer_drift(self):
        """把 expect 改成源码里不存在的字面量，自检必须失败——证明不是摆设。"""
        original = dict(ENTRIES[0])
        try:
            ENTRIES[0]["producer"] = "scripts/route_expert.py"
            ENTRIES[0]["expect"] = "THIS_FILE_DOES_NOT_EXIST.json"
            ENTRIES[0]["kind"] = "file"
            errs = validate()
            self.assertTrue(any("清单与代码漂移" in x for x in errs), errs)
        finally:
            ENTRIES[0] = original
        self.assertEqual(validate(), [])

    def test_derived_layer_is_never_manual(self):
        original = dict(next(e for e in ENTRIES if e["layer"] == "派生层"))
        idx = next(i for i, e in enumerate(ENTRIES) if e["layer"] == "派生层")
        try:
            ENTRIES[idx]["write"] = "manual"
            self.assertTrue(any("派生层不得人工维护" in x for x in validate()))
        finally:
            ENTRIES[idx] = original

    def test_render_is_deterministic_and_synced(self):
        self.assertEqual(render_md(), render_md())
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "FILE_LAYOUT.md"
            p = cli("--emit-md", str(out))
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(out.read_text(encoding="utf-8"), render_md())
            committed = ROOT / "docs" / "generated" / "FILE_LAYOUT.md"
            self.assertEqual(out.read_text(encoding="utf-8"),
                             committed.read_text(encoding="utf-8"),
                             "生成物与清单漂移：重跑 --emit-md 并提交")
        for e in ENTRIES:
            self.assertIn(f"`{e['path']}`", render_md())
        for x in NOT_IN_TARGET:
            self.assertIn(x["reason"], render_md())

    def test_ledger_fields_are_not_files(self):
        self.assertTrue(any("lifecycle.log" in f["path"] for f in LEDGER_FIELDS))
        self.assertNotIn("governance/lifecycle.log", {e["path"] for e in ENTRIES})
        self.assertIn("不是 governance/lifecycle.log 文件", render_md())


class LayoutDiffTest(unittest.TestCase):

    def test_demo_is_governed_and_diff_is_readonly(self):
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            before = tree_hash(proj)
            p = cli("--diff", "--target", str(proj), "--json")
            self.assertEqual(p.returncode, 0, p.stderr)
            d = json.loads(p.stdout)
            self.assertEqual(d["schema"], "file-layout-diff/1")
            self.assertEqual(d["phase"], "governed")
            self.assertEqual(d["missing_required"], [])
            self.assertEqual(d["unexpected"], [])
            self.assertIn("governance/run_tests.py", d["added_present"])
            self.assertEqual(d["target_label"], ".")  # 不泄露绝对路径
            self.assertEqual(tree_hash(proj), before, "--diff 不得写任何文件")
            self.assertEqual(cli("--diff", "--target", str(proj), "--strict").returncode, 0)

    def test_empty_project_is_bootstrap(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            d = diff(root)
            self.assertEqual(d["phase"], "bootstrap")
            self.assertIn("governance/registry.json", d["missing_required"])
            self.assertIn("governance/", d["missing_required"])
            self.assertEqual(d["unexpected"], [])
            self.assertEqual(cli("--diff", "--target", str(root), "--strict").returncode, 2)

    def test_greenfield_bootstrap_has_six_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = subprocess.run([sys.executable, str(INIT), "--target", str(root),
                                "--code", "NEW", "--name", "新项目"],
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            gov = root / "governance"
            self.assertEqual(sorted(f.name for f in gov.iterdir() if f.is_file()),
                             ["DECISION_LEDGER.json", "build_capability_model.py",
                              "index.html", "registry.json", "run_tests.py",
                              "verify_ledger.py"])
            d = diff(root)
            self.assertEqual(d["phase"], "skeleton")
            self.assertEqual(d["missing_required"], [])
            self.assertEqual(d["unexpected"], [])
            self.assertEqual(cli("--diff", "--target", str(root), "--strict").returncode, 0)

    def test_brownfield_draft_is_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "src" / "domain").mkdir(parents=True)
            (root / "src" / "domain" / "billing.py").write_text("x = 1\n", encoding="utf-8")
            p = subprocess.run([sys.executable, str(DISCOVER), "--target", str(root)],
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            d = diff(root)
            present = {r["path"] for r in d["rows"] if r["exists"]}
            self.assertIn("governance/registry.draft.json", present)
            self.assertIn("governance/ADOPTION_REPORT.md", present)
            # 草稿层不是越界文件，且尚未接入时仍是 bootstrap
            self.assertEqual(d["unexpected"], [])
            self.assertEqual(d["phase"], "bootstrap")

    def test_unexpected_governance_file_is_flagged(self):
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            (proj / "governance" / "STATUS.md").write_text("# 另一份状态\n", encoding="utf-8")
            d = diff(proj)
            self.assertIn("governance/STATUS.md", d["unexpected"])
            self.assertEqual(cli("--diff", "--target", str(proj), "--strict").returncode, 2)

    def test_ignored_cache_is_not_unexpected(self):
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            cache = proj / "governance" / "__pycache__"
            cache.mkdir(exist_ok=True)
            (cache / "x.pyc").write_bytes(b"\x00")
            (proj / "governance" / ".DS_Store").write_bytes(b"\x00")
            self.assertEqual(diff(proj)["unexpected"], [])

    def test_missing_target_fails_closed(self):
        p = cli("--diff", "--target", "/definitely/not/a/project")
        self.assertEqual(p.returncode, 2)
        self.assertIn("目标目录不存在", p.stderr)


if __name__ == "__main__":
    unittest.main()
