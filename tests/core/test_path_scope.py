"""路径全集契约：账本只能引用仓库里有的东西（v2.0.3）。

负向证明而非正向声明：这些用例先造出「本机有、仓库没有」的文件与目录，
再断言它们绝对不会出现在账本里。正向断言（引用的路径存在）已经由
verify_ledger 的 doc_paths_exist / component_paths_exist 负责，这里只证明
生成器不会把仓库外的东西写进账本。
"""
MODULE_ID = "core"

import subprocess
import tempfile
import unittest
from pathlib import Path

from _base import ROOT  # noqa: F401  确保 sys.path 指向 templates/

import build_capability_model as B


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True,
                   capture_output=True)


def _flatten(nodes) -> list[str]:
    out: list[str] = []
    for n in nodes:
        for child in n.get("children", []) or []:
            if child.get("path"):
                out.append(child["path"])
            out.extend(_flatten([child]))
        if n.get("path"):
            out.append(n["path"])
    return out


class RepoScopeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="scope-"))
        root = self.tmp
        (root / "src" / "domain").mkdir(parents=True)
        (root / "src" / "domain" / "order.py").write_text("X = 1\n")
        (root / "tests" / "unit").mkdir(parents=True)
        (root / "tests" / "unit" / "test_order.py").write_text("X = 1\n")
        # 本机存在但未入库：临时测试与运行产物目录
        (root / "tests" / "unit" / "test_scratch.py").write_text("X = 1\n")
        for rel in ("data/reports", "logs", "src/ares.egg-info"):
            (root / rel).mkdir(parents=True)
            (root / rel / "out.txt").write_text("noise\n")
        (root / ".gitignore").write_text("data/\nlogs/\n*.egg-info/\n")
        _git(root, "init", "-q")
        _git(root, "add", ".gitignore", "src/domain/order.py", "tests/unit/test_order.py")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_tracked_paths_are_visible(self):
        scope = B.RepoScope(self.tmp)
        self.assertTrue(scope.verified)
        self.assertTrue(scope.has_file("src/domain/order.py"))
        self.assertTrue(scope.has_dir("src/domain"))

    def test_untracked_file_is_invisible(self):
        scope = B.RepoScope(self.tmp)
        self.assertFalse(scope.has_file("tests/unit/test_scratch.py"))
        # 反证：文件确实躺在磁盘上，排除「本来就找不到」的假通过
        self.assertTrue((self.tmp / "tests/unit/test_scratch.py").is_file())

    def test_runtime_artifact_dirs_are_invisible(self):
        scope = B.RepoScope(self.tmp)
        for rel in ("data", "data/reports", "logs", "src/ares.egg-info"):
            self.assertFalse(scope.has_dir(rel), f"{rel} 不该进入账本")

    def test_component_tree_skips_untracked(self):
        scope = B.RepoScope(self.tmp)
        tree = B.build_component_tree(self.tmp, self.tmp, ["src/", "data/"], {}, scope=scope)
        paths = _flatten(tree)
        self.assertIn("src/domain", paths)
        self.assertIn("src/domain/order.py", paths)
        for noise in ("data", "logs", "src/ares.egg-info"):
            self.assertNotIn(noise, paths)

    def test_glob_files_skips_untracked(self):
        scope = B.RepoScope(self.tmp)
        hits = B.glob_files(self.tmp / "tests", ["unit/"], scope)
        names = {p.name for p in hits}
        self.assertIn("test_order.py", names)
        self.assertNotIn("test_scratch.py", names)

    def test_report_binding_untracked_test_is_not_fresh(self):
        """报告绑定了未入库测试：本机摘要对得上，别人也复现不了——不算新鲜证据。"""
        import hashlib
        rel = "tests/unit/test_scratch.py"
        digest = hashlib.sha256((self.tmp / rel).read_bytes()).hexdigest()
        report = {"evidence_binding": {
            "algorithm": "sha256-files-v1",
            "inputs": [{"path": rel, "sha256": digest}],
        }}
        scope = B.RepoScope(self.tmp)
        ok, detail = B.check_freshness(report, self.tmp, "", scope)
        self.assertFalse(ok)
        self.assertTrue(detail.startswith("untracked:"), detail)
        # 反证：不传 scope（旧行为）会把它当成 fresh，说明这条守卫真的在起作用
        self.assertTrue(B.check_freshness(report, self.tmp, "")[0])

    def test_non_git_dir_degrades_visibly(self):
        """没有 git 时可退回文件系统全集，但必须自报未核对，绝不假装已验证。"""
        import shutil
        bare = Path(tempfile.mkdtemp(prefix="nogit-"))
        self.addCleanup(shutil.rmtree, bare, True)
        (bare / "anything.py").write_text("X = 1\n")
        scope = B.RepoScope(bare)
        self.assertFalse(scope.verified)
        self.assertTrue(scope.why)
        self.assertTrue(scope.has_file("whatever.py"))


if __name__ == "__main__":
    unittest.main()
