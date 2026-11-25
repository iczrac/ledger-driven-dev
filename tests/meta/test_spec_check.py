"""规范型仓库通用自查器：五类判据、0 与 n/a 口径、等效只读的负向证明。"""
from __future__ import annotations
MODULE_ID = "meta"

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _base import ROOT

SPEC_CHECK = ROOT / "scripts" / "spec_check.py"


def cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SPEC_CHECK), *args],
                          capture_output=True, text=True)


def make_repo(td: Path, config: dict, files: dict[str, str]) -> Path:
    target = td / "repo"
    target.mkdir()
    (target / "spec_check.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=1), encoding="utf-8")
    for rel, text in files.items():
        p = target / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return target


BASE = {"schema": "spec-check/1"}


class SpecCheckCLITest(unittest.TestCase):

    def test_missing_config_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            empty = Path(td) / "empty"
            empty.mkdir()
            p = cli("--target", str(empty))
            self.assertEqual(p.returncode, 2, p.stderr)

    def test_bad_schema_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            t = make_repo(Path(td), {"schema": "wrong/1"}, {})
            p = cli("--target", str(t))
            self.assertEqual(p.returncode, 2, p.stderr)

    def test_empty_config_all_na_exit_0(self):
        with tempfile.TemporaryDirectory() as td:
            t = make_repo(Path(td), dict(BASE), {"README.md": "# hi\n"})
            p = cli("--target", str(t))
            self.assertEqual(p.returncode, 0, p.stdout)
            d = json.loads(cli("--target", str(t), "--json").stdout)
            self.assertEqual(d["schema"], "spec-check/1")
            self.assertTrue(d["ok"])
            self.assertEqual(d["applicable"], 0)
            self.assertEqual(d["na"], 5)
            for m in d["metrics"]:
                self.assertFalse(m["applicable"])


class TermResidueTest(unittest.TestCase):

    def test_ascii_word_boundary_avoids_cjk_false_negative(self):
        # 核心教训：`\\b` 把汉字当词符，「Rick標注」必须命中；「Tricky」不得误伤。
        cfg = {**BASE, "forbidden_terms": ["Rick"]}
        with tempfile.TemporaryDirectory() as td:
            t = make_repo(Path(td), cfg, {"docs/a.md": "Rick標注了需求，Tricky 保留\n"})
            d = json.loads(cli("--target", str(t), "--json").stdout)
            terms = [m for m in d["metrics"] if m["metric"] == "forbidden_terms"][0]
            self.assertTrue(terms["applicable"])
            self.assertEqual(terms["hits"], 1)
            self.assertEqual(terms["detail"][0]["count"], 1)
            self.assertEqual(cli("--target", str(t)).returncode, 1)

    def test_cjk_substring_term(self):
        cfg = {**BASE, "forbidden_terms": ["旧名"]}
        with tempfile.TemporaryDirectory() as td:
            t = make_repo(Path(td), cfg, {"a.md": "这里写着旧名，旧名又出现\n"})
            d = json.loads(cli("--target", str(t), "--json").stdout)
            terms = [m for m in d["metrics"] if m["metric"] == "forbidden_terms"][0]
            self.assertEqual(terms["hits"], 1)
            self.assertEqual(terms["detail"][0]["count"], 2)

    def test_exclude_paths_honored(self):
        cfg = {**BASE, "forbidden_terms": ["Ghost"],
               "scan": {"exclude": ["dist/**"]}}
        with tempfile.TemporaryDirectory() as td:
            t = make_repo(Path(td), cfg,
                          {"docs/a.md": "clean\n", "dist/b.md": "Ghost\n"})
            d = json.loads(cli("--target", str(t), "--json").stdout)
            terms = [m for m in d["metrics"] if m["metric"] == "forbidden_terms"][0]
            self.assertEqual(terms["hits"], 0)


class VersionConsistencyTest(unittest.TestCase):

    def test_mismatch_detected(self):
        cfg = {**BASE, "version": {"canonical": "2.0.0", "declarations": [
            {"file": "plugin.json", "json_key": "version"},
            {"file": "README.md", "regex": r"版本\s+([0-9][\w.]*)"},
        ]}}
        files = {"plugin.json": '{"version": "2.0.0"}',
                 "README.md": "版本 1.9.0 发布\n"}
        with tempfile.TemporaryDirectory() as td:
            t = make_repo(Path(td), cfg, files)
            d = json.loads(cli("--target", str(t), "--json").stdout)
            ver = [m for m in d["metrics"] if m["metric"] == "version"][0]
            self.assertTrue(ver["applicable"])
            self.assertEqual(ver["declarations_checked"], 2)
            self.assertEqual(ver["hits"], 1)
            self.assertEqual(ver["detail"][0]["found"], "1.9.0")

    def test_canonical_from_json(self):
        cfg = {**BASE, "version": {"canonical_from": {
            "file": "plugin.json", "json_key": "version"},
            "declarations": [{"file": "plugin.json", "json_key": "version"}]}}
        with tempfile.TemporaryDirectory() as td:
            t = make_repo(Path(td), cfg, {"plugin.json": '{"version": "3.1.4"}'})
            d = json.loads(cli("--target", str(t), "--json").stdout)
            ver = [m for m in d["metrics"] if m["metric"] == "version"][0]
            self.assertEqual(ver["canonical"], "3.1.4")
            self.assertEqual(ver["hits"], 0)


class GeneratedDriftTest(unittest.TestCase):

    def test_rebuild_side_effect_detected_and_restored(self):
        rebuild_py = (
            "from pathlib import Path\n"
            # parents=True：部分环境的 mkdir shim 不认非 recursive 的 exist_ok
            "Path('dist').mkdir(parents=True, exist_ok=True)\n"
            "Path('dist/out.md').write_text('generated\\n', encoding='utf-8')\n"
            "p = Path('dist/existing.md')\n"
            "p.write_text('TAMPERED\\n', encoding='utf-8')\n"
        )
        cfg = {**BASE, "generated": {"rebuild_cmd": [sys.executable, "rebuild.py"],
                                     "paths": ["dist"]}}
        with tempfile.TemporaryDirectory() as td:
            t = make_repo(Path(td), cfg,
                          {"rebuild.py": rebuild_py,
                           "dist/existing.md": "original\n"})
            d = json.loads(cli("--target", str(t), "--json").stdout)
            gen = [m for m in d["metrics"] if m["metric"] == "generated_drift"][0]
            self.assertTrue(gen["applicable"])
            self.assertEqual(gen["hits"], 2, f"detail={gen.get('detail')}")
            states = {x["file"]: x["state"] for x in gen["detail"]}
            self.assertEqual(states["dist/out.md"], "created")
            self.assertEqual(states["dist/existing.md"], "changed")
            self.assertEqual(gen["restored"], 1)
            self.assertEqual(gen["removed"], 1)
            # 等效只读：检查后 dist 恢复原样
            self.assertEqual((t / "dist" / "existing.md").read_text(encoding="utf-8"),
                             "original\n")
            self.assertFalse((t / "dist" / "out.md").exists())

    def test_no_drift_exit_0(self):
        rebuild_py = "print('noop')\n"
        cfg = {**BASE, "generated": {"rebuild_cmd": [sys.executable, "rebuild.py"],
                                     "paths": ["dist"]}}
        with tempfile.TemporaryDirectory() as td:
            t = make_repo(Path(td), cfg,
                          {"rebuild.py": rebuild_py, "dist/a.md": "keep\n"})
            d = json.loads(cli("--target", str(t), "--json").stdout)
            self.assertTrue(d["ok"])
            gen = [m for m in d["metrics"] if m["metric"] == "generated_drift"][0]
            self.assertEqual(gen["hits"], 0)

    def test_no_rebuild_flag_skips(self):
        cfg = {**BASE, "generated": {"rebuild_cmd": [sys.executable, "missing.py"],
                                     "paths": ["dist"]}}
        with tempfile.TemporaryDirectory() as td:
            t = make_repo(Path(td), cfg, {})
            d = json.loads(cli("--target", str(t), "--json", "--no-rebuild").stdout)
            gen = [m for m in d["metrics"] if m["metric"] == "generated_drift"][0]
            self.assertIn("skipped", gen.get("note", ""))


class RequiredAndLinksTest(unittest.TestCase):

    def test_required_missing_and_broken_link(self):
        cfg = {**BASE,
               "required": ["README.md", "docs/evolution.md"],
               "links": {"docs": ["README.md"]}}
        files = {"README.md": "[历史](docs/history.md)\n"}
        with tempfile.TemporaryDirectory() as td:
            t = make_repo(Path(td), cfg, files)
            d = json.loads(cli("--target", str(t), "--json").stdout)
            req = [m for m in d["metrics"] if m["metric"] == "required_files"][0]
            links = [m for m in d["metrics"] if m["metric"] == "broken_links"][0]
            self.assertEqual(req["hits"], 1)
            self.assertEqual(req["detail"][0]["file"], "docs/evolution.md")
            self.assertEqual(links["links_checked"], 1)
            self.assertEqual(links["hits"], 1)
            self.assertEqual(links["detail"][0]["link"], "docs/history.md")
            self.assertEqual(cli("--target", str(t)).returncode, 1)

    def test_external_links_not_checked(self):
        cfg = {**BASE, "links": {"docs": ["README.md"]}}
        files = {"README.md": "[x](https://a.b/c) [y](mailto:z@a) [s](#anchor)\n"}
        with tempfile.TemporaryDirectory() as td:
            t = make_repo(Path(td), cfg, files)
            d = json.loads(cli("--target", str(t), "--json").stdout)
            links = [m for m in d["metrics"] if m["metric"] == "broken_links"][0]
            self.assertEqual(links["links_checked"], 0)
            self.assertEqual(links["hits"], 0)


if __name__ == "__main__":
    unittest.main()
