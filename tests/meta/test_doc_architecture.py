"""docs 文件架构规范化：三类文档分层、双作用域 generated、路径与编号口径一致。"""
MODULE_ID = "meta"
import unittest
from pathlib import Path

from _base import ROOT


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class DocArchitectureTest(unittest.TestCase):
    def test_scaffold_docstring_uses_plural_plans(self):
        """doc-lifecycle scaffold 是给目标项目用的，路径须与 file_layout 的 docs/plans/ 一致。"""
        s = read("scripts/doc_lifecycle.py")
        self.assertNotIn("docs/plan/", s, "单数 docs/plan/ 与 file_layout 的 docs/plans/ 冲突")
        self.assertIn("docs/plans/", s)

    def test_standard_distinguishes_two_generated_scopes(self):
        """STANDARD 第六节须区分方法仓自带 generated 与目标项目 generated，不能混列。"""
        s = read("docs/STANDARD.md")
        section = s.split("## 六、生成文档目录", 1)[1].split("## 七、", 1)[0]
        self.assertIn("目标项目", section)
        self.assertIn("方法论仓库", section)
        for f in ("PROJECT_BRIEF.md", "MODULE_MAP.md", "CAPABILITY_INDEX.md", "GRAPH_DIFF.md"):
            self.assertIn(f, section)
        for f in ("ONTOLOGY.md", "TEST_MODULES.md", "FILE_LAYOUT.md"):
            self.assertIn(f, section)

    def test_file_layout_no_stale_01_21_range(self):
        """file_layout 与 15-文件架构 不得再写过时的 docs/01-21（实际已 01-36）。"""
        for f in ("scripts/file_layout.py", "docs/15-文件架构.md"):
            self.assertNotIn("docs/01-21", read(f), f"{f} 仍写 01-21")

    def test_numbered_docs_are_contiguous(self):
        """编号方法论文档须连续，无缺口（规范化基线）。"""
        import re
        nums = sorted(int(m.group(1)) for p in (ROOT / "docs").glob("[0-9][0-9]-*.md")
                      if (m := re.match(r"(\d+)-", p.name)))
        self.assertEqual(nums, list(range(1, max(nums) + 1)))
        self.assertEqual(len(nums), 36)

    def test_readme_index_covers_all_numbered_docs(self):
        """README 人工索引须覆盖全部编号方法论文档，避免索引与权威源脱节。"""
        import re
        readme = read("README.md")
        listed = set(re.findall(r"docs/(\d\d)-[^)]*\.md", readme))
        all_nums = {p.name[:2] for p in (ROOT / "docs").glob("[0-9][0-9]-*.md")}
        self.assertEqual(sorted(all_nums - listed), [], "README 漏列文档编号")

    def test_three_layers_physically_separated(self):
        """人工编号文档 / STANDARD / generated 派生三层须物理隔离。"""
        self.assertTrue((ROOT / "docs" / "STANDARD.md").is_file())
        self.assertTrue((ROOT / "docs" / "generated").is_dir())
        self.assertFalse((ROOT / "docs" / "01-问题与原则.md").read_text().strip().startswith("<!--"))
