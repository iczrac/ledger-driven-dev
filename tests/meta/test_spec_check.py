"""规范型仓库通用自查器：七类判据、0 与 n/a 口径、等效只读的负向证明。"""
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
            self.assertEqual(d["na"], 7)
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


class OntologyIntegrityTest(unittest.TestCase):
    """本体判据：id 唯一、引用可解析、别名不冲突、路径映射落真。"""

    CFG = {**BASE, "ontology": {
        "files": ["onto/*.json"],
        "ref_fields": ["consumes", "members"],
        "path_fields": ["platforms"],
    }}

    ACTORS = {
        "schema": "julia-ledger-onto/0.1",
        "actors": [
            {"id": "actor.julia", "name": "Julia", "aliases": [], "kind": "lead",
             "platforms": {"claude-code": "agents/lead.md"}},
            {"id": "actor.remy", "name": "Remy", "aliases": ["Mike"], "kind": "specialist",
             "platforms": {"claude-code": "agents/remy.md", "hermes": None},
             "consumes": ["actor.julia"]},
        ],
    }

    def _metric(self, target):
        d = json.loads(cli("--target", str(target), "--json").stdout)
        return [m for m in d["metrics"] if m["metric"] == "ontology_integrity"][0]

    def test_good_registry_passes_exit_0(self):
        with tempfile.TemporaryDirectory() as td:
            t = make_repo(Path(td), self.CFG, {
                "onto/actors.json": json.dumps(self.ACTORS, ensure_ascii=False),
                "agents/lead.md": "x\n", "agents/remy.md": "x\n",
            })
            m = self._metric(t)
            self.assertTrue(m["applicable"])
            self.assertEqual(m["hits"], 0, f"detail={m.get('detail')}")
            self.assertEqual(m["ids_declared"], 2)
            self.assertEqual(cli("--target", str(t)).returncode, 0)

    def test_duplicate_id_and_unresolved_ref(self):
        actors = {"actors": [
            {"id": "actor.a", "name": "A"},
            {"id": "actor.a", "name": "A2"},
            {"id": "actor.b", "name": "B", "members": ["actor.ghost"]},
        ]}
        with tempfile.TemporaryDirectory() as td:
            t = make_repo(Path(td), self.CFG,
                          {"onto/actors.json": json.dumps(actors)})
            m = self._metric(t)
            reasons = {x["reason"] for x in m["detail"]}
            self.assertIn("duplicate_id", reasons)
            self.assertIn("unresolved_ref", reasons)
            self.assertEqual(cli("--target", str(t)).returncode, 1)

    def test_alias_collides_with_existing_name(self):
        # 核心场景：改名后旧名若仍被另一角色占用，必须命中
        actors = {"actors": [
            {"id": "actor.x", "name": "Mark", "aliases": ["Rick"]},
            {"id": "actor.y", "name": "Rick"},
        ]}
        with tempfile.TemporaryDirectory() as td:
            t = make_repo(Path(td), self.CFG,
                          {"onto/actors.json": json.dumps(actors)})
            m = self._metric(t)
            reasons = {x["reason"] for x in m["detail"]}
            self.assertIn("alias_collides_with_name", reasons)
            self.assertEqual(cli("--target", str(t)).returncode, 1)

    def test_platform_mapping_missing_path(self):
        actors = {"actors": [{"id": "actor.a", "name": "A",
                              "platforms": {"claude-code": "agents/nope.md"}}]}
        with tempfile.TemporaryDirectory() as td:
            t = make_repo(Path(td), self.CFG,
                          {"onto/actors.json": json.dumps(actors)})
            m = self._metric(t)
            self.assertEqual(m["hits"], 1)
            self.assertEqual(m["detail"][0]["reason"], "missing_path")

    def test_invalid_json_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            t = make_repo(Path(td), self.CFG, {"onto/actors.json": "{broken"})
            m = self._metric(t)
            self.assertEqual(m["hits"], 1)
            self.assertEqual(m["detail"][0]["reason"], "invalid_json")

    def test_missing_config_is_na(self):
        with tempfile.TemporaryDirectory() as td:
            t = make_repo(Path(td), dict(BASE), {"README.md": "x\n"})
            m = self._metric(t)
            self.assertFalse(m["applicable"])


def _git_repo_with_tag(t: Path, tag: str | None) -> None:
    """在目标目录建一个最小 git 仓（tag 需要指向 commit）。"""
    def run(*a: str):
        subprocess.run(["git", "-c", "init.defaultBranch=main", *a], cwd=t,
                       capture_output=True, text=True, check=True)
    run("init", "-q")
    run("add", "spec_check.json")
    run("-c", "user.email=t@local", "-c", "user.name=t", "commit", "-qm", "init")
    if tag:
        run("tag", tag)


class ReleaseTagTest(unittest.TestCase):
    """发版标签判据：权威版本必须有对应 git tag；非 git / 无版本 fail-closed。"""

    def _metric(self, target):
        d = json.loads(cli("--target", str(target), "--json").stdout)
        return [m for m in d["metrics"] if m["metric"] == "release_tag"][0]

    def test_tag_present_passes_exit_0(self):
        cfg = {**BASE, "version": {"canonical": "1.2.3"},
               "release_tag": {"prefix": "v"}}
        with tempfile.TemporaryDirectory() as td:
            t = make_repo(Path(td), cfg, {"README.md": "x\n"})
            _git_repo_with_tag(t, "v1.2.3")
            m = self._metric(t)
            self.assertTrue(m["applicable"])
            self.assertEqual(m["hits"], 0)
            self.assertEqual(m["tag"], "v1.2.3")
            self.assertEqual(cli("--target", str(t)).returncode, 0)

    def test_tag_missing_hits(self):
        cfg = {**BASE, "version": {"canonical": "9.9.9"},
               "release_tag": {"prefix": "v"}}
        with tempfile.TemporaryDirectory() as td:
            t = make_repo(Path(td), cfg, {"README.md": "x\n"})
            _git_repo_with_tag(t, None)
            m = self._metric(t)
            self.assertEqual(m["hits"], 1)
            self.assertEqual(m["detail"][0]["reason"], "missing_tag")
            self.assertEqual(cli("--target", str(t)).returncode, 1)

    def test_non_git_repo_fails_closed(self):
        cfg = {**BASE, "version": {"canonical": "1.0.0"},
               "release_tag": {}}
        with tempfile.TemporaryDirectory() as td:
            t = make_repo(Path(td), cfg, {"README.md": "x\n"})
            m = self._metric(t)
            self.assertEqual(m["hits"], 1)
            self.assertEqual(m["detail"][0]["reason"], "not_a_git_repo")

    def test_release_tag_without_version_fails_closed(self):
        cfg = {**BASE, "release_tag": {}}
        with tempfile.TemporaryDirectory() as td:
            t = make_repo(Path(td), cfg, {"README.md": "x\n"})
            _git_repo_with_tag(t, "v0.1.0")
            m = self._metric(t)
            self.assertEqual(m["hits"], 1)
            self.assertEqual(m["detail"][0]["reason"], "no_canonical_version")

    def test_custom_prefix(self):
        cfg = {**BASE, "version": {"canonical": "2.0.0"},
               "release_tag": {"prefix": "rel-"}}
        with tempfile.TemporaryDirectory() as td:
            t = make_repo(Path(td), cfg, {"README.md": "x\n"})
            _git_repo_with_tag(t, "rel-2.0.0")
            m = self._metric(t)
            self.assertEqual(m["hits"], 0)

    def test_missing_config_is_na(self):
        with tempfile.TemporaryDirectory() as td:
            t = make_repo(Path(td), dict(BASE), {"README.md": "x\n"})
            m = self._metric(t)
            self.assertFalse(m["applicable"])


if __name__ == "__main__":
    unittest.main()
