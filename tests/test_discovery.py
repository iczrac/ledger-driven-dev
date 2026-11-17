"""存量项目发现：只读、确定性、非破坏性。"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _base import ROOT
from discover_project import SCHEMA, discover, render_report, sanitize_code

DISCOVER = ROOT / "scripts" / "discover_project.py"
_TEMP_DIRS: list[str] = []


def make_project(files: dict[str, str]) -> Path:
    root = Path(tempfile.mkdtemp())
    _TEMP_DIRS.append(str(root))
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return root


class DiscoveryTest(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        for path in _TEMP_DIRS:
            shutil.rmtree(path, ignore_errors=True)

    def test_sanitize_code(self):
        self.assertEqual(sanitize_code("order-api"), "ORDER_API")
        self.assertEqual(sanitize_code("123abc"), "X_123ABC")
        self.assertEqual(sanitize_code("###"), "ITEM")

    def test_discover_groups_by_source_root(self):
        root = make_project({
            "src/domain/order.py": "class Order: pass\n",
            "src/api/order_api.py": "def api(): pass\n",
            "tests/unit/test_order.py": "def test_order(): pass\n",
            "docs/plans/ORDER_PLAN.md": "# plan\n",
            "node_modules/pkg/index.js": "module.exports = {}\n",
            "governance/DECISION_LEDGER.json": "{}",
        })
        draft = discover(root)
        self.assertEqual(draft["_discovery"]["schema"], SCHEMA)
        self.assertEqual(draft["_discovery"]["counts"]["source"], 2)
        self.assertEqual(draft["_discovery"]["counts"]["test"], 1)
        codes = [m["code"] for m in draft["modules"]]
        self.assertEqual(codes, ["API", "DOMAIN"])
        caps = [c for m in draft["modules"] for c in m["caps"]]
        self.assertEqual(len(caps), 2)
        for cap in caps:
            self.assertTrue((root / cap["impl"][0]).exists())
            self.assertEqual(cap["hints"], [h.lower() for h in cap["hints"]])

    def test_discover_empty_project_warns_and_is_deterministic(self):
        root = make_project({"README.md": "# 空项目\n"})
        a = discover(root)
        b = discover(root)
        self.assertEqual(a, b)
        self.assertEqual(a["modules"], [{"code": "CORE", "name": "核心能力",
                                          "src": [], "caps": []}])
        self.assertTrue(any("源码" in w for w in a["_discovery"]["warnings"]))
        self.assertEqual(a["_discovery"]["confidence"], "low")

    def test_max_caps_is_bounded(self):
        files = {f"src/mod/file_{i:02d}.py": "x = 1\n" for i in range(12)}
        root = make_project(files)
        draft = discover(root, max_caps=3)
        self.assertEqual(len(draft["modules"][0]["caps"]), 3)
        self.assertTrue(any("前 3 个" in w for w in draft["_discovery"]["warnings"]))

    def test_report_has_no_absolute_paths(self):
        root = make_project({"src/a.py": "x=1\n"})
        report = render_report(discover(root))
        self.assertNotIn(str(root), report)
        self.assertNotIn("/Users/", report)
        self.assertIn("只读扫描", report)

    def test_cli_writes_then_respects_existing_then_force(self):
        root = make_project({
            "src/domain/order.py": "x=1\n",
            "tests/test_order.py": "def test_order(): pass\n",
        })
        cmd = [sys.executable, str(DISCOVER), "--target", str(root)]
        first = subprocess.run(cmd, capture_output=True, text=True, check=True)
        self.assertIn("写入:", first.stdout)
        draft_path = root / "governance" / "registry.draft.json"
        report_path = root / "governance" / "ADOPTION_REPORT.md"
        self.assertTrue(draft_path.exists())
        self.assertTrue(report_path.exists())
        original = draft_path.read_text()
        second = subprocess.run(cmd, capture_output=True, text=True, check=True)
        self.assertIn("跳过（已存在", second.stdout)
        self.assertEqual(draft_path.read_text(), original)
        forced = subprocess.run(cmd + ["--force"], capture_output=True, text=True, check=True)
        self.assertIn("写入:", forced.stdout)
        data = json.loads(draft_path.read_text())
        self.assertEqual(data["project"]["governance_gate"], False)
        self.assertTrue(data["modules"][0]["src"][0].endswith("/"))

    def test_dry_run_does_not_write(self):
        root = make_project({"src/a.py": "x=1\n"})
        subprocess.run([sys.executable, str(DISCOVER), "--target", str(root), "--dry-run"],
                       capture_output=True, text=True, check=True)
        self.assertFalse((root / "governance").exists())

    def test_json_cli_is_valid(self):
        root = make_project({"src/a.py": "x=1\n"})
        proc = subprocess.run([sys.executable, str(DISCOVER), "--target", str(root), "--json"],
                              capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(proc.stdout)["_discovery"]["schema"], SCHEMA)


if __name__ == "__main__":
    unittest.main()
