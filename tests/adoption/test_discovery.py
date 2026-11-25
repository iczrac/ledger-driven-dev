"""存量项目发现：只读、确定性、非破坏性。"""
MODULE_ID = "adoption"
import json
import re
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
        self.assertEqual(sanitize_code("order-api"), "ORDERAPI")
        self.assertEqual(sanitize_code("123abc"), "X123ABC")
        self.assertEqual(sanitize_code("###"), "ITEM")
        # 生成的每个段都必须满足四段码契约（A 项：不透传下划线）。
        segment = re.compile(r"[A-Z][A-Z0-9]*")
        for raw in ("order-api", "secret_sync", "123abc", "a b/c", "###"):
            self.assertTrue(segment.fullmatch(sanitize_code(raw)), raw)

    def test_discover_draft_codes_obey_contract(self):
        root = make_project({
            "src/shadow/secret_sync.py": "def sync(): return 1\n",
            "tests/test_a.py": "def test_a(): pass\n",
        })
        draft = discover(root)
        self.assertEqual(draft["modules"][0]["code"], "SHADOW")
        self.assertEqual(draft["modules"][0]["caps"][0]["domain"], "SECRETSYNC")
        code = f"{draft['project']['code']}.{draft['modules'][0]['code']}." \
               f"{draft['modules'][0]['caps'][0]['domain']}.01"
        self.assertRegex(code, r"^[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9]*\.\d{2}$")

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


class SpecRepoDiscoveryTest(unittest.TestCase):
    """v2.29.0 spec-repo 模式：文档型仓库以 SKILL.md/agents 为能力点候选。"""

    def _discover(self, files):
        root = make_project(files)
        return discover(root)

    def test_spec_repo_detected_and_modules_built(self):
        d = self._discover({
            "README.md": "# 规范仓库\n",
            "plugin.json": '{"version": "1.0.0"}',
            "scripts/build_dist.py": "print('x')\n",
            "agents/remy.md": "# Remy\n",
            "agents/lead.md": "# Julia\n",
            "skills/deep-diff-review/SKILL.md": "# 深查\n",
            "skills/ledger-bridge/SKILL.md": "# 桥\n",
        })
        self.assertEqual(d["_discovery"]["source"], "filesystem-only/spec-repo")
        codes = {m["code"] for m in d["modules"]}
        self.assertIn("TEAM", codes)
        self.assertIn("SKILLS", codes)
        self.assertIn("INFRA", codes)
        skills = [m for m in d["modules"] if m["code"] == "SKILLS"][0]
        domains = {c["domain"] for c in skills["caps"]}
        self.assertIn("DEEPDIFFREVIEW", domains)
        self.assertIn("LEDGERBRIDGE", domains)
        team = [m for m in d["modules"] if m["code"] == "TEAM"][0]
        self.assertEqual({c["domain"] for c in team["caps"]}, {"REMY", "LEAD"})

    def test_code_repo_not_misdetected(self):
        d = self._discover({
            "README.md": "# app\n",
            "src/core/order.py": "class Order:\n",
            "src/core/pay.py": "def pay():\n",
            "tests/test_order.py": "pass\n",
        })
        self.assertEqual(d["_discovery"]["source"], "filesystem-only")
        self.assertNotIn("TEAM", {m["code"] for m in d["modules"]})

    def test_spec_mode_confidence_medium(self):
        d = self._discover({
            "agents/remy.md": "# R\n",
            "skills/bridge/SKILL.md": "# B\n",
        })
        self.assertEqual(d["_discovery"]["confidence"], "medium")
        self.assertGreaterEqual(d["_discovery"]["candidate_caps"], 2)
