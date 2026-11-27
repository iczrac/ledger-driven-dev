"""架构图纸引擎命令行入口（标准库 argparse）。

    python3 -m blueprint.cli scan  --root <path> [--registry <path>] [--ext .py] [--out <graph.json>]
    python3 -m blueprint.cli render --graph <g.json> [--overrides <o.json>] [--out <diagram.svg>]
    python3 -m blueprint.cli map   --graph <g.json> [--focus <node_id>] [--out <map.html>]
    python3 -m blueprint.cli focus --graph <g.json> --node <id> [--node <id> ...] [--out <focus.svg>]
    python3 -m blueprint.cli impact --graph <g.json> --node <id> [--node <id> ...] [--out <impact.json>]
    python3 -m blueprint.cli diff  --before <g1.json> --after <g2.json> [--out <diff.svg>]
    python3 -m blueprint.cli check --graph <g.json>
    python3 -m blueprint.cli --check --graph <g.json>

    map   ：地图式——系统 + 模块一屏看完，点模块卡片展开组件，--focus 高亮某节点。
    focus ：聚焦式——以 --node 为中心画同心环，红＝被依赖、蓝＝包含，一眼看波及谁。

退出码：0 成功 / 1 参数错误（含文件不存在、JSON 解析失败）/ 2 校验失败。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .graph import apply_overrides, build_from_source, check_graph, impact_up
from .render import render_diff, render_focus, render_map, render_svg


class _Parser(argparse.ArgumentParser):
    """把 argparse 默认的退出码 2 改成派工单要求的「参数错误 = 1」。"""

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: 参数错误：{message}\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="python3 -m blueprint.cli",
                     description="架构图纸引擎（四层图纸 / 地图式 / 聚焦式 + 向上影响传导）")
    parser.add_argument("--check", action="store_true", help="配合顶层 --graph 校验图合法性")
    parser.add_argument("--graph", dest="top_graph", help="顶层 --check 要校验的 graph JSON")
    sub = parser.add_subparsers(dest="cmd")

    scan = sub.add_parser("scan", help="从源码 + 可选 registry 自动推导图纸")
    scan.add_argument("--root", required=True, help="源码根目录")
    scan.add_argument("--registry", help="可选 registry.json（补能力层）")
    scan.add_argument("--ext", action="append", help="扫描扩展名，可重复，默认 .py")
    scan.add_argument("--out", help="输出 graph JSON 路径；省略则 stdout")
    scan.add_argument("--check", action="store_true", help="产出后校验，不合法则退出 2 且不落盘")

    render = sub.add_parser("render", help="把图纸渲染成单文件 SVG")
    render.add_argument("--graph", required=True, help="graph JSON 路径")
    render.add_argument("--overrides", help="人确认修正 JSON（叠加且修正优先）")
    render.add_argument("--out", help="输出 SVG 路径；省略则 stdout")
    render.add_argument("--check", action="store_true", help="渲染前校验，不合法则退出 2")

    impact = sub.add_parser("impact", help="沿 contains 边向上列出受影响节点与路径")
    impact.add_argument("--graph", required=True, help="graph JSON 路径")
    impact.add_argument("--node", action="append", required=True, help="底层节点 id，可重复")
    impact.add_argument("--out", help="输出 impact JSON 路径；省略则 stdout")
    impact.add_argument("--check", action="store_true", help="计算前校验，不合法则退出 2")

    map_view = sub.add_parser("map", help="地图式 HTML：系统 + 模块一屏看完，点击展开组件")
    map_view.add_argument("--graph", required=True, help="graph JSON 路径")
    map_view.add_argument("--focus", help="可选，要高亮并默认展开的节点 id")
    map_view.add_argument("--out", help="输出 HTML 路径；省略则 stdout")
    map_view.add_argument("--check", action="store_true", help="渲染前校验，不合法则退出 2")

    focus = sub.add_parser("focus", help="聚焦式 SVG：以被改节点为中心，红=被依赖 / 蓝=包含")
    focus.add_argument("--graph", required=True, help="graph JSON 路径")
    focus.add_argument("--node", action="append", required=True, help="被改的节点 id，可重复")
    focus.add_argument("--out", help="输出 SVG 路径；省略则 stdout")
    focus.add_argument("--check", action="store_true", help="计算前校验，不合法则退出 2")

    diff = sub.add_parser("diff", help="现状图 vs 规划图 SVG（绿新增/红删除/黄修改）")
    diff.add_argument("--before", required=True, help="现状图 graph JSON")
    diff.add_argument("--after", required=True, help="规划图 graph JSON（人确认修正后）")
    diff.add_argument("--out", help="输出 diff SVG 路径；省略则 stdout")
    diff.add_argument("--check", action="store_true", help="渲染前校验两图，不合法则退出 2")

    check = sub.add_parser("check", help="校验 graph JSON：id 唯一 / 边端点存在 / 无环")
    check.add_argument("--graph", required=True, help="graph JSON 路径")
    return parser


def _load(path: str | Path) -> dict:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"文件不存在：{p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _emit(text: str, out: str | None) -> int:
    if out:
        Path(out).write_text(text, encoding="utf-8")
        print(f"已写入 {out}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def _do_check(graph: object) -> tuple[int, dict]:
    errors = check_graph(graph)
    result = {
        "schema": "blueprint-check/1",
        "ok": not errors,
        "nodes": len(graph.get("nodes", [])) if isinstance(graph, dict) else 0,
        "edges": len(graph.get("edges", [])) if isinstance(graph, dict) else 0,
        "errors": errors,
    }
    return (0 if not errors else 2), result


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))

    try:
        # 顶层 --check --graph <path>
        if args.check and not args.cmd:
            if not args.top_graph:
                parser.error("顶层 --check 需要 --graph <path>（或用 check 子命令）")
            code, result = _do_check(_load(args.top_graph))
            sys.stdout.write(_json(result))
            return code

        if args.cmd == "scan":
            graph = build_from_source(
                Path(args.root),
                Path(args.registry) if args.registry else None,
                tuple(args.ext) if args.ext else (".py",),
            )
            code, result = _do_check(graph)
            if args.check and code != 0:
                sys.stderr.write(_json(result))
                return 2
            return _emit(_json(graph), args.out)

        if args.cmd == "render":
            graph = _load(args.graph)
            if args.overrides:
                graph = apply_overrides(graph, Path(args.overrides))
            code, result = _do_check(graph)
            if args.check and code != 0:
                sys.stderr.write(_json(result))
                return 2
            return _emit(render_svg(graph), args.out)

        if args.cmd == "impact":
            graph = _load(args.graph)
            code, result = _do_check(graph)
            if args.check and code != 0:
                sys.stderr.write(_json(result))
                return 2
            return _emit(_json(impact_up(graph, args.node)), args.out)

        if args.cmd == "map":
            graph = _load(args.graph)
            code, result = _do_check(graph)
            if args.check and code != 0:
                sys.stderr.write(_json(result))
                return 2
            return _emit(render_map(graph, args.focus), args.out)

        if args.cmd == "focus":
            graph = _load(args.graph)
            code, result = _do_check(graph)
            if args.check and code != 0:
                sys.stderr.write(_json(result))
                return 2
            return _emit(render_focus(impact_up(graph, args.node), graph), args.out)

        if args.cmd == "diff":
            before, after = _load(args.before), _load(args.after)
            if args.check:
                for g in (before, after):
                    code, result = _do_check(g)
                    if code != 0:
                        sys.stderr.write(_json(result))
                        return 2
            return _emit(render_diff(before, after), args.out)

        if args.cmd == "check":
            code, result = _do_check(_load(args.graph))
            sys.stdout.write(_json(result))
            return code

        parser.print_help()
        return 0
    except (OSError, ValueError, TypeError) as exc:
        # JSONDecodeError 是 ValueError 子类；文件不存在 OSError → 均按参数错误处理。
        print(f"参数错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
