"""新建与存量接入：非破坏性初始化、来源可追溯、生成后可校验。"""
MODULE_ID = "adoption"
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _base import ROOT
from board_path import resolve as board_resolve

INIT = ROOT / "scripts" / "init_project.py"
DISCOVER = ROOT / "scripts" / "discover_project.py"
GENERATOR = ROOT / "templates" / "build_capability_model.py"
VERIFIER = ROOT / "templates" / "verify_ledger.py"
_TEMP_DIRS: list[str] = []


def make_dir(files: dict[str, str] | None = None) -> Path:
    root = Path(tempfile.mkdtemp())
    _TEMP_DIRS.append(str(root))
    for rel, content in (files or {}).items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return root


def run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *map(str, args)],
                          capture_output=True, text=True)


class BootstrapTest(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        for path in _TEMP_DIRS:
            shutil.rmtree(path, ignore_errors=True)

    def test_greenfield_creates_skeleton_with_provenance(self):
        root = make_dir()
        proc = run(INIT, "--target", root, "--code", "NEW", "--name", "新项目")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        gov = root / "governance"
        for name in ("registry.json", "DECISION_LEDGER.json", board_resolve(gov).name,
                     "build_capability_model.py", "verify_ledger.py",
                     "registry_codec.py", "run_tests.py", "board_path.py"):
            self.assertTrue((gov / name).exists(), name)
        reg = json.loads((gov / "registry.json").read_text())
        ledger = json.loads((gov / "DECISION_LEDGER.json").read_text())
        self.assertEqual(reg["project"]["code"], "NEW")
        self.assertEqual(reg["project"]["root"], ".")
        self.assertEqual(ledger["provenance"]["mode"], "greenfield")
        self.assertEqual(ledger["provenance"]["source"], "template")
        self.assertEqual(ledger["entries"][0]["id"], "D-001")

    def test_greenfield_drops_example_declarations(self):
        """示例里的 tests/test_records 指向 demo 文件，新项目没有——不能原样带过去。"""
        root = make_dir()
        proc = run(INIT, "--target", root, "--code", "NEW", "--name", "新项目")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        reg = json.loads((root / "governance/registry.json").read_text())
        for module in reg["modules"]:
            for cap in module["caps"]:
                self.assertNotIn("tests", cap)
                self.assertNotIn("test_records", cap)
                self.assertIn("hints", cap)

    def test_adopt_consumes_draft_without_touching_it(self):
        root = make_dir({
            "src/domain/order.py": "class Order: pass\n",
            "tests/test_order.py": "def test_order(): pass\n",
        })
        self.assertEqual(run(DISCOVER, "--target", root).returncode, 0)
        draft_path = root / "governance" / "registry.draft.json"
        before = draft_path.read_text()
        proc = run(INIT, "--target", root, "--mode", "adopt", "--code", "LEG",
                   "--intent", "接手历史项目")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(draft_path.read_text(), before)
        reg = json.loads((root / "governance" / "registry.json").read_text())
        ledger = json.loads((root / "governance" / "DECISION_LEDGER.json").read_text())
        self.assertEqual([m["code"] for m in reg["modules"]], ["DOMAIN"])
        self.assertEqual(ledger["provenance"]["mode"], "adopt")
        self.assertEqual(ledger["provenance"]["source"], "governance/registry.draft.json")
        self.assertEqual(ledger["provenance"]["intent"], "接手历史项目")
        self.assertGreater(ledger["provenance"]["discovery"]["counts"]["source"], 0)
        self.assertIn("只读发现", ledger["entries"][0]["rationale"])
        self.assertNotIn(str(root), (root / "governance" / "DECISION_LEDGER.json").read_text())
        self.assertNotIn("/Users/", (root / "governance" / "DECISION_LEDGER.json").read_text())

    def test_adopt_without_draft_fails_closed(self):
        root = make_dir({"src/a.py": "x=1\n"})
        proc = run(INIT, "--target", root, "--mode", "adopt", "--code", "LEG")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("discover_project.py", proc.stderr + proc.stdout)
        self.assertFalse((root / "governance" / "registry.json").exists())

    def test_adopt_illegal_code_fails_closed_with_actionable_message(self):
        root = make_dir()
        gov = root / "governance"
        gov.mkdir()
        draft = {
            "project": {"code": "LEG", "name": "Legacy", "root": "."},
            "modules": [{"code": "SHADOW", "name": "Shadow", "src": ["src/shadow/"],
                         "caps": [{"name": "Secret Sync", "domain": "SECRET_SYNC",
                                   "impl": ["src/shadow/secret_sync.py"]}]}],
        }
        (gov / "registry.draft.json").write_text(json.dumps(draft))
        proc = run(INIT, "--target", root, "--mode", "adopt", "--code", "LEG")
        self.assertEqual(proc.returncode, 2)
        msg = proc.stderr + proc.stdout
        self.assertIn("registry.draft.json", msg)
        self.assertIn("SECRET_SYNC", msg)
        self.assertIn("SECRETSYNC", msg)
        self.assertIn("四段式", msg)
        self.assertFalse((gov / "registry.json").exists())

    def test_existing_files_are_not_overwritten(self):
        root = make_dir()
        gov = root / "governance"
        gov.mkdir()
        marker = gov / "DECISION_LEDGER.json"
        marker.write_text('{"marker": "keep"}')
        proc = run(INIT, "--target", root, "--code", "NEW")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(marker.read_text(), '{"marker": "keep"}')
        self.assertIn("跳过（已存在）", proc.stdout)

    def test_adopted_project_generates_and_verifies(self):
        root = make_dir({
            "src/domain/order.py": "class Order: pass\n",
            "tests/test_order.py": "def test_order(): pass\n",
        })
        self.assertEqual(run(DISCOVER, "--target", root).returncode, 0)
        self.assertEqual(run(INIT, "--target", root, "--mode", "adopt", "--code", "LEG").returncode, 0)
        gov = root / "governance"
        gen = run(GENERATOR, "--root", root, "--registry", gov / "registry.json",
                  "--ledger", gov / "DECISION_LEDGER.json", "--board", board_resolve(gov))
        self.assertEqual(gen.returncode, 0, gen.stderr)
        ver = run(VERIFIER, "--root", root, "--registry", gov / "registry.json",
                  "--ledger", gov / "DECISION_LEDGER.json", "--board", board_resolve(gov),
                  "--strict")
        self.assertEqual(ver.returncode, 0, ver.stdout + ver.stderr)
        ledger = json.loads((gov / "DECISION_LEDGER.json").read_text())
        self.assertEqual(len(ledger["history"]["events"]), 1)
        self.assertTrue(ledger["capability_model"]["projects"])


if __name__ == "__main__":
    unittest.main()
