"""架构图纸引擎最小切片的定向测试（含负向探针）。

刻意不改 tests/MODULES.json：本文件只供 `python3 -m unittest discover -s tests/blueprint`
定向运行。若全量门禁的 stage_test_modules / stage_tests 因「未登记模块」报红，
属预期发现，需由主理人决策，不得在此自行绕过。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from blueprint.cli import main as cli_main
from blueprint.graph import (apply_overrides, build_from_source, check_graph,
                             impact_up, valid_code)
from blueprint.render import render_diff, render_focus, render_map, render_svg

REPO_ROOT = Path(__file__).resolve().parents[2]


class BlueprintGraphTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "mod_a").mkdir()
        (self.root / "mod_b").mkdir()
        (self.root / "mod_a" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "mod_a" / "beta.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
        (self.root / "mod_a" / "alpha.py").write_text(
            "from mod_a.beta import helper\nimport mod_a.beta\nthing = helper()\n",
            encoding="utf-8")
        # 负向探针：注释与字符串里的伪 import 都不是 AST Import 节点
        (self.root / "mod_b" / "gamma.py").write_text(
            "from mod_a.alpha import thing\n"
            "# import phantom.ghost\n"
            "note = 'import phantom.ghost'\n",
            encoding="utf-8")
        self.registry = self.root / "registry.json"
        self.registry.write_text(json.dumps({
            "project": {"code": "METHOD", "name": "示例系统"},
            "modules": [{"code": "GOV", "name": "治理", "caps": [{
                "code": "METHOD.GOV.FEEDBACK.01", "name": "反馈通道",
                "domain": "FEEDBACK", "impl": ["mod_a/alpha.py"]}]}],
        }, ensure_ascii=False), encoding="utf-8")
        self.graph = build_from_source(self.root, self.registry)

    def _ids(self) -> set[str]:
        return {n["id"] for n in self.graph["nodes"]}

    def _edges(self, kind: str) -> set[tuple[str, str]]:
        return {(e["from"], e["to"]) for e in self.graph["edges"] if e["kind"] == kind}

    # ---------- 自动推导 ----------
    def test_schema_and_layers(self) -> None:
        self.assertEqual(self.graph["schema"], "blueprint-graph/1")
        self.assertEqual(self.graph["root"], ".")
        types = {n["type"] for n in self.graph["nodes"]}
        self.assertEqual(types, {"component", "module", "capability", "system"})

    def test_contains_edges(self) -> None:
        contains = self._edges("contains")
        self.assertIn(("system:root", "module:mod_a"), contains)
        self.assertIn(("module:mod_a", "component:mod_a/alpha.py"), contains)
        self.assertIn(("system:root", "capability:METHOD.GOV.FEEDBACK.01"), contains)
        self.assertIn(("capability:METHOD.GOV.FEEDBACK.01", "component:mod_a/alpha.py"), contains)
        self.assertEqual(check_graph(self.graph), [])

    def test_depends_edges_from_ast(self) -> None:
        depends = self._edges("depends")
        self.assertIn(("component:mod_a/alpha.py", "component:mod_a/beta.py"), depends)
        self.assertIn(("component:mod_b/gamma.py", "component:mod_a/alpha.py"), depends)

    def test_negative_fake_import_not_extracted(self) -> None:
        ids = self._ids()
        for frm, to in self._edges("depends"):
            self.assertIn(frm, ids)
            self.assertIn(to, ids)
            self.assertNotIn("phantom", frm + to)
        self.assertFalse(any("phantom" in e["to"] for e in self.graph["edges"]))

    def test_determinism_and_no_absolute_paths(self) -> None:
        self.assertEqual(self.graph, build_from_source(self.root, self.registry))
        dump = json.dumps(self.graph, ensure_ascii=False)
        self.assertNotIn(str(self.root), dump)
        for node in self.graph["nodes"]:
            if node["path"]:
                self.assertFalse(node["path"].startswith("/"))

    def test_capability_name_not_raw_code(self) -> None:
        cap = next(n for n in self.graph["nodes"] if n["type"] == "capability")
        self.assertEqual(cap["label"], "反馈通道")
        self.assertTrue(valid_code(cap["meta"]["code"]))

    # ---------- 人确认修正 ----------
    def _overrides(self, ops: list[dict]) -> Path:
        path = self.root / "overrides.json"
        path.write_text(json.dumps({"schema": "blueprint-overrides/1", "ops": ops},
                                   ensure_ascii=False), encoding="utf-8")
        return path

    def test_override_add_node(self) -> None:
        out = apply_overrides(self.graph, self._overrides([
            {"op": "add_node", "node": {"id": "component:manual.md", "type": "component",
                                        "label": "人工补充组件", "path": "manual.md"}}]))
        self.assertIn("component:manual.md", {n["id"] for n in out["nodes"]})

    def test_override_add_edge(self) -> None:
        out = apply_overrides(self.graph, self._overrides([
            {"op": "add_edge", "from": "component:mod_b/gamma.py",
             "to": "component:mod_a/beta.py", "kind": "depends"}]))
        self.assertIn(("component:mod_b/gamma.py", "component:mod_a/beta.py"),
                      {(e["from"], e["to"]) for e in out["edges"] if e["kind"] == "depends"})

    def test_override_remove_edge(self) -> None:
        out = apply_overrides(self.graph, self._overrides([
            {"op": "remove_edge", "from": "module:mod_b",
             "to": "component:mod_b/gamma.py", "kind": "contains"}]))
        self.assertNotIn(("module:mod_b", "component:mod_b/gamma.py"),
                         {(e["from"], e["to"]) for e in out["edges"] if e["kind"] == "contains"})

    def test_override_precedence(self) -> None:
        # 同 id 的 add_node 整条替换自动节点；add_edge + remove_edge 时 remove 最后生效。
        out = apply_overrides(self.graph, self._overrides([
            {"op": "add_node", "node": {"id": "module:mod_a", "type": "module",
                                        "label": "人工改名的模块", "path": "mod_a"}},
            {"op": "add_edge", "from": "system:root", "to": "capability:METHOD.GOV.FEEDBACK.01",
             "kind": "depends"},
            {"op": "remove_edge", "from": "system:root",
             "to": "capability:METHOD.GOV.FEEDBACK.01", "kind": "depends"},
        ]))
        self.assertEqual(next(n["label"] for n in out["nodes"] if n["id"] == "module:mod_a"),
                         "人工改名的模块")
        self.assertNotIn("depends", [e["kind"] for e in out["edges"]
                                     if e["from"] == "system:root"
                                     and e["to"] == "capability:METHOD.GOV.FEEDBACK.01"])

    # ---------- 影响传导 ----------
    @staticmethod
    def _paths_to(result: dict, node_id: str) -> list[tuple[list[str], list[str], str]]:
        for entries in result["by_level"].values():
            for entry in entries:
                if entry["id"] == node_id:
                    return list(zip(entry["paths"], entry["path_kinds"], entry["path_labels"]))
        return []

    def test_impact_up(self) -> None:
        result = impact_up(self.graph, ["component:mod_a/alpha.py"])
        by_level = result["by_level"]
        self.assertIn("module", by_level)
        self.assertIn("capability", by_level)
        self.assertIn("system", by_level)
        cap = by_level["capability"][0]
        self.assertEqual(cap["label"], "反馈通道")
        self.assertEqual(cap["paths"][0][0], "component:mod_a/alpha.py")
        self.assertIn("反馈通道", cap["path_labels"][0])
        self.assertEqual(cap["path_kinds"][0], ["contains"])
        self.assertEqual(result["seeds"], ["component:mod_a/alpha.py"])

    def test_impact_reverse_depends(self) -> None:
        # fixture: alpha depends beta；gamma depends alpha。
        # 改 beta 必须波及直接依赖者 alpha 与传递依赖者 gamma。
        result = impact_up(self.graph, ["component:mod_a/beta.py"])
        alpha = self._paths_to(result, "component:mod_a/alpha.py")
        gamma = self._paths_to(result, "component:mod_b/gamma.py")
        self.assertTrue(alpha)
        self.assertTrue(gamma)
        self.assertTrue(any(kinds == ["depends"] for _, kinds, _ in alpha))
        self.assertTrue(any(kinds == ["depends", "depends"] for _, kinds, _ in gamma))
        self.assertTrue(any("被依赖" in label for _, _, label in alpha))
        # 依赖者的 contains 上卷也要出现：系统层存在含 depends 段的影响路径
        system = self._paths_to(result, "system:root")
        self.assertTrue(any("depends" in kinds for _, kinds, _ in system))
        self.assertIn("depends", result["relation_legend"])

    def test_impact_mixed_contains_and_depends_path(self) -> None:
        result = impact_up(self.graph, ["component:mod_a/beta.py"])
        mixed = [(p, k, lab) for p, k, lab in self._paths_to(result, "module:mod_a")
                 if k == ["depends", "contains"]]
        self.assertTrue(mixed, "应存在 depends 反向 + contains 上卷的复合路径")
        _, _, label = mixed[0]
        self.assertIn("被依赖", label)
        self.assertIn("包含", label)

    def test_impact_no_false_depends(self) -> None:
        # gamma 没有任何依赖者；depends 只能反向走，不能正向回溯到它依赖的 alpha。
        result = impact_up(self.graph, ["component:mod_b/gamma.py"])
        all_ids = {e["id"] for entries in result["by_level"].values() for e in entries}
        self.assertNotIn("component:mod_a/alpha.py", all_ids)
        for entries in result["by_level"].values():
            for entry in entries:
                self.assertNotIn("depends", entry["via"])
                self.assertTrue(all(k == "contains" for k in
                                    [step for kinds in entry["path_kinds"] for step in kinds]))

    def test_impact_cycle_terminates_with_visited(self) -> None:
        graph = {
            "schema": "blueprint-graph/1", "root": ".",
            "nodes": [
                {"id": "component:a.py", "type": "component", "label": "a.py",
                 "path": "a.py", "meta": {}},
                {"id": "component:b.py", "type": "component", "label": "b.py",
                 "path": "b.py", "meta": {}},
            ],
            "edges": [
                {"from": "component:a.py", "to": "component:b.py", "kind": "depends"},
                {"from": "component:b.py", "to": "component:a.py", "kind": "depends"},
            ],
        }
        result = impact_up(graph, ["component:b.py"])   # 有环也必须终止
        affected = [e for entries in result["by_level"].values() for e in entries
                    if e["id"] == "component:a.py"]
        self.assertEqual(len(affected), 1)
        for path in affected[0]["paths"]:
            self.assertEqual(len(path), len(set(path)), "visited set 应阻止路径重复访问节点")

    # ---------- 渲染 ----------
    def test_render_svg_valid_and_human_readable(self) -> None:
        svg = render_svg(self.graph, highlight=["component:mod_a/alpha.py"])
        self.assertTrue(svg.startswith("<svg"))
        root = ET.fromstring(svg)  # XML 可解析
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertIn("反馈通道", svg)
        self.assertIn("alpha.py", svg)
        self.assertIn("受影响", svg)
        self.assertNotIn("METHOD.GOV.FEEDBACK.01", svg)  # 主标签不暴露能力码原文

    def test_render_diff(self) -> None:
        after = apply_overrides(self.graph, self._overrides([
            {"op": "add_node", "node": {"id": "component:plan.md", "type": "component",
                                        "label": "规划组件", "path": "plan.md"}},
            {"op": "remove_edge", "from": "module:mod_b",
             "to": "component:mod_b/gamma.py", "kind": "contains"}]))
        svg = render_diff(self.graph, after)
        self.assertTrue(svg.startswith("<svg"))
        ET.fromstring(svg)
        self.assertIn("新增", svg)
        self.assertIn("删除", svg)

    # ---------- 负向：环 / 悬空边 / --check 红 ----------
    def test_check_detects_cycle(self) -> None:
        graph = json.loads(json.dumps(self.graph))
        graph["edges"].extend([
            {"from": "module:mod_a", "to": "module:mod_b", "kind": "depends"},
            {"from": "module:mod_b", "to": "module:mod_a", "kind": "depends"},
        ])
        errors = check_graph(graph)
        self.assertTrue(any("检测到环" in e for e in errors))

    def test_negative_dangling_edge_fails_check(self) -> None:
        graph = json.loads(json.dumps(self.graph))
        graph["edges"].append({"from": "module:mod_a", "to": "component:ghost.py",
                               "kind": "contains"})
        errors = check_graph(graph)
        self.assertTrue(any("引用不存在的终点节点" in e for e in errors))
        path = self.root / "broken.json"
        path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
        code = cli_main(["check", "--graph", str(path)])
        self.assertEqual(code, 2)
        proc = subprocess.run(
            [sys.executable, "-m", "blueprint.cli", "--check", "--graph", str(path)],
            cwd=str(REPO_ROOT), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)

    def test_cli_scan_and_render_end_to_end(self) -> None:
        graph_path = self.root / "scan.json"
        self.assertEqual(cli_main(["scan", "--root", str(self.root),
                                   "--registry", str(self.registry), "--out", str(graph_path)]), 0)
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        self.assertGreater(len(graph["nodes"]), 5)
        svg_path = self.root / "diagram.svg"
        self.assertEqual(cli_main(["render", "--graph", str(graph_path), "--out", str(svg_path)]), 0)
        self.assertTrue(svg_path.read_text(encoding="utf-8").startswith("<svg"))


class BlueprintViewsTest(unittest.TestCase):
    """新增的地图式 / 聚焦式视角测试（含空图负向探针）。"""

    def setUp(self) -> None:
        self.seed = "component:core/seed.py"
        self.graph = {
            "schema": "blueprint-graph/1", "root": ".",
            "nodes": [
                {"id": "system:root", "type": "system", "label": "示例系统",
                 "path": "", "meta": {}},
                {"id": "module:core", "type": "module", "label": "核心模块",
                 "path": "core", "meta": {}},
                {"id": "capability:DEMO.CORE.01", "type": "capability", "label": "核心能力",
                 "path": "", "meta": {"code": "DEMO.CORE.01"}},
                {"id": self.seed, "type": "component", "label": "seed.py",
                 "path": "core/seed.py", "meta": {}},
                {"id": "component:core/user.py", "type": "component", "label": "user.py",
                 "path": "core/user.py", "meta": {}},
            ],
            "edges": [
                {"from": "system:root", "to": "module:core", "kind": "contains"},
                {"from": "system:root", "to": "capability:DEMO.CORE.01", "kind": "contains"},
                {"from": "module:core", "to": self.seed, "kind": "contains"},
                {"from": "module:core", "to": "component:core/user.py", "kind": "contains"},
                {"from": "capability:DEMO.CORE.01", "to": self.seed, "kind": "contains"},
                {"from": "component:core/user.py", "to": self.seed, "kind": "depends"},
            ],
        }

    def test_render_map_valid_html(self) -> None:
        html = render_map(self.graph)
        self.assertIn("<html", html)
        self.assertIn("示例系统", html)
        self.assertIn("核心模块", html)
        self.assertIn("function toggle(", html)      # 点击钻取用的原生 JS
        self.assertIn("核心能力", html)               # 组件标注中文能力名
        self.assertNotIn("DEMO.CORE.01", html)        # 不暴露能力码原文

    def test_render_focus_valid_svg(self) -> None:
        svg = render_focus(impact_up(self.graph, [self.seed]), self.graph)
        root = ET.fromstring(svg)                     # XML 可解析
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertIn("seed.py", svg)                 # 中心 seed 名
        self.assertIn("user.py", svg)                 # 受影响的反向依赖者
        self.assertIn("#c62828", svg)                 # 红 = 被依赖
        self.assertIn("#1f6fb2", svg)                 # 蓝 = 包含
        self.assertIn("[被依赖]", svg)
        self.assertIn("[包含]", svg)
        self.assertIn("改这里会影响 1 个组件、1 个模块", svg)

    def test_render_map_focus_highlight(self) -> None:
        plain = render_map(self.graph)
        focused = render_map(self.graph, focus=self.seed)
        self.assertNotIn('class="card focus-module"', plain)
        self.assertIn('class="card focus-module"', focused)   # 所在模块高亮
        self.assertIn('<span class="badge-focus">聚焦</span>', focused)  # 可见标记
        self.assertIn('class="comp focus-node"', focused)     # 节点本身高亮
        self.assertIn('style="display:block"', focused)       # 聚焦模块默认展开

    def test_render_empty_graph_no_crash(self) -> None:
        empty = {"schema": "blueprint-graph/1", "root": ".", "nodes": [], "edges": []}
        html = render_map(empty)
        self.assertIn("<html", html)
        self.assertIn("未命名系统", html)
        svg = render_focus(impact_up(empty, [self.seed]), empty)
        self.assertEqual(ET.fromstring(svg).tag, "{http://www.w3.org/2000/svg}svg")

    def test_cli_map_focus_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            graph_path = root / "graph.json"
            graph_path.write_text(json.dumps(self.graph, ensure_ascii=False), encoding="utf-8")
            map_path, focus_path = root / "map.html", root / "focus.svg"
            self.assertEqual(cli_main(["map", "--graph", str(graph_path),
                                       "--focus", self.seed, "--out", str(map_path)]), 0)
            self.assertIn("focus-module", map_path.read_text(encoding="utf-8"))
            self.assertEqual(cli_main(["focus", "--graph", str(graph_path),
                                       "--node", self.seed, "--out", str(focus_path)]), 0)
            self.assertEqual(ET.fromstring(focus_path.read_text(encoding="utf-8")).tag,
                             "{http://www.w3.org/2000/svg}svg")


if __name__ == "__main__":
    unittest.main()
