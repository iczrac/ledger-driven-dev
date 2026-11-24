#!/usr/bin/env python3
"""规划图 vs 实际图比对：能力级 diff + 专家规划的开发顺序。

规划图来自 TARGET_ARCHITECTURE.json（文档 → 目标），缺失时退回 registry；
实际图来自账本 capability_model（证据 → 现状）。两者按四段式编码对齐，
输出可机读 GRAPH_DIFF.json 与人类可读 GRAPH_DIFF.md。

用法：
    python3 scripts/compare_graphs.py --target /path/to/project --dry-run
    python3 scripts/compare_graphs.py --target . --git-trace governance/GIT_TRACE.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from trace_common import (artifact_paths, canonical_code, iter_caps, load_json,
                          rel_path, write_if_absent)

try:
    from route_expert import build as route_build
except ImportError:  # 单独复制脚本到项目时使用
    route_build = None  # type: ignore[assignment]

# warnings 是人读摘要，避免几十组同义异码把 stdout 撑爆；JSON 保留全量 pairs。
MAX_WARN_SHADOW_PAIRS = 5


def _short_module(code: str) -> str:
    parts = str(code).split(".")
    return parts[1] if len(parts) > 1 else str(code)


def _level_num(value: str | int | None) -> int:
    if value is None:
        return 5
    s = str(value)
    return int(s[1:]) if s.startswith("L") and s[1:].isdigit() else 0


def build(target: Path, registry: dict, ledger: dict, target_arch: dict | None,
          git_trace: dict) -> dict:
    warnings: list[str] = []
    # plan_status 让下游一眼区分「无规划 / 空规划 / 部分规划 / 有效规划」。
    # absent 与 empty 时漂移结论不可采信，必须显式告知，不得静默当成有效规划。
    if target_arch:
        planned_caps = target_arch.get("capabilities", [])
        planned_modules = target_arch.get("modules", [])
        plan_source = "TARGET_ARCHITECTURE.json"
        if not planned_caps:
            plan_status = "empty" if not planned_modules else "partial"
        elif not planned_modules:
            plan_status = "partial"
        else:
            plan_status = "present"
    else:
        plan_status = "absent"
        planned_caps = [
            {"code": c["code"], "name": c["name"], "target_level": None,
             "depends_on": [], "sources": ["registry.json"]}
            for c in iter_caps(registry, ledger)
        ]
        planned_modules = [
            {"code": m.get("code", ""), "name": m.get("name", ""),
             "src": m.get("src", []), "caps": []}
            for m in registry.get("modules", [])
        ]
        plan_source = "registry.json (fallback)"
        warnings.append("未找到目标架构；以 registry 作为规划图，建议先运行 architect_from_docs.py。")

    if plan_status in ("absent", "empty", "partial"):
        warnings.append(
            f"目标规划图状态为 {plan_status}（缺失/为空/不完整），本报告的漂移结论不可采信；"
            "请先用 architect_from_docs.py 生成有效规划图后再复核。")
    plan_trustworthy = plan_status == "present"

    plan_by_code = {str(c.get("code", "")): c for c in planned_caps if c.get("code")}
    cm = ledger.get("capability_model", {})
    actual_by_code: dict[str, dict] = {}
    actual_modules: dict[str, dict] = {}
    for p in cm.get("projects", []):
        for m in p.get("modules", []):
            short = _short_module(m.get("code", ""))
            actual_modules[short] = {
                "code": m.get("code", ""), "name": m.get("name", ""),
                "completion": m.get("completion", 0),
                "component_count": len(m.get("component_tree", []) or []),
            }
            for c in m.get("caps", []):
                if c.get("code"):
                    actual_by_code[c["code"]] = c

    # shadow 对齐只做提示：字面码仍分别是 planned_only / actual_only，
    # 不自动合并、不改等级、不放宽任何硬门禁。
    plan_canonical: dict[str, list[str]] = {}
    actual_canonical: dict[str, list[str]] = {}
    for code in plan_by_code:
        key = canonical_code(code)
        if key:
            plan_canonical.setdefault(key, []).append(code)
    for code in actual_by_code:
        key = canonical_code(code)
        if key:
            actual_canonical.setdefault(key, []).append(code)
    shadow_pairs: list[dict] = []
    for key in sorted(set(plan_canonical) & set(actual_canonical)):
        for planned_code in plan_canonical[key]:
            for actual_code in actual_canonical[key]:
                if planned_code != actual_code:
                    shadow_pairs.append({"canonical": key, "planned": planned_code,
                                         "actual": actual_code})
    shadow_by_code: dict[str, list[str]] = {}
    for pair in shadow_pairs:
        shadow_by_code.setdefault(pair["planned"], []).append(pair["actual"])
        shadow_by_code.setdefault(pair["actual"], []).append(pair["planned"])
    if shadow_pairs:
        shown = shadow_pairs[:MAX_WARN_SHADOW_PAIRS]
        described = "；".join(f"{p['planned']} ↔ {p['actual']}" for p in shown)
        if len(shadow_pairs) > len(shown):
            described += f"；其余 {len(shadow_pairs) - len(shown)} 组见 JSON.shadow_pairs"
        warnings.append(f"发现 {len(shadow_pairs)} 组疑似同一能力（仅编码写法不同）："
                        f"{described}；仅提示，不自动合并。")

    # D 项：语义别名（同义异码）配对。canonical_code 只覆盖格式变体，
    # 这里用 impl 路径集合做「疑似同一能力」的 shadow 配对：
    # - 规划侧 impl_hint 来自 CAPABILITY_INDEX 代码列（账本投影，非第二事实源）
    # - 实际侧用 artifact_paths 的 code 集合
    # - 仅当同模块且 impl 集合相同/有交集时配对
    # 硬约束：只写入 shadow_pairs / warnings / alias_matches，
    # 不改 status / level / 不自动合并（语义推断误报风险高，按 shadow 纪律只晒不否决）。
    impl_planned: dict[str, set[str]] = {}
    impl_actual: dict[str, set[str]] = {}
    for code, plan in plan_by_code.items():
        paths = {"/".join(str(x).strip("` ").split("/")[-3:])
                 for x in (plan.get("impl_hint") or [])}
        if paths:
            impl_planned[code] = paths
    for code, live in actual_by_code.items():
        # 实际侧 doc_index 路径可能带「examples/<项目>/」等仓库相对前缀，
        # 而 CAPABILITY_INDEX 的路径相对项目根。用「保留最后 3 段」归一化：
        # 任一路径都可与其后缀对齐，避免依赖具体项目目录名。
        paths = {"/".join(str(rel_path(x, target)).split("/")[-3:])
                 for x in artifact_paths(live).get("code", [])}
        if paths:
            impl_actual[code] = paths

    # 已被 canonical 配对的（格式变体）不再重复报 alias，避免同一对双报。
    canonical_pairs = {(p["planned"], p["actual"]) for p in shadow_pairs}
    alias_pairs: list[dict] = []
    alias_by_code: dict[str, list[str]] = {}
    for pcode, pimpl in sorted(impl_planned.items()):
        pmodule = _short_module(pcode)
        for acode, aimpl in sorted(impl_actual.items()):
            if pcode == acode or (pcode, acode) in canonical_pairs:
                continue
            if _short_module(acode) != pmodule:
                continue
            if not (pimpl == aimpl or pimpl & aimpl):
                continue
            pair = {"kind": "alias_suspect", "planned": pcode, "actual": acode,
                    "impl": sorted(pimpl & aimpl or pimpl),
                    "reason": "同模块且 impl 路径相同/有交集，疑似同义异码；仅提示，不自动合并"}
            alias_pairs.append(pair)
            alias_by_code.setdefault(pcode, []).append(acode)
            alias_by_code.setdefault(acode, []).append(pcode)
    if alias_pairs:
        shadow_pairs.extend(alias_pairs)
        shown = "；".join(f"{p['planned']} ↔ {p['actual']}"
                         for p in alias_pairs[:MAX_WARN_SHADOW_PAIRS])
        warnings.append(f"发现 {len(alias_pairs)} 组同义异码疑似（_impl 路径相同/交集）："
                        f"{shown}；仅提示，不自动合并、不改状态与等级。")

    commits_by_code: dict[str, list[str]] = {}
    for commit in git_trace.get("commits", []):
        for code in commit.get("cap_codes", []):
            commits_by_code.setdefault(code, []).append(commit.get("hash", ""))

    comparison: list[dict] = []
    all_codes = sorted(set(plan_by_code) | set(actual_by_code))
    for code in all_codes:
        plan = plan_by_code.get(code)
        live = actual_by_code.get(code)
        target_level = str((plan or {}).get("target_level") or "L5")
        target_num = _level_num(target_level)
        if plan and not live:
            status, gaps = "planned_only", ["尚未被生成器识别", "补 impl / hints 或先实现证据"]
        elif live and not plan:
            status, gaps = "actual_only", ["实际存在但规划图未声明", "补文档或裁决是否废弃"]
        else:
            level = int(live.get("level", 0) or 0)
            if level == 0:
                status, gaps = "not_started", ["无 L1 契约证据"]
            elif level < target_num:
                status = "in_progress"
                gaps = list(live.get("next_action", "").split("；")) if live.get("next_action") else []
            else:
                status, gaps = "aligned", []
            if live.get("evidence_tier") == "declared" and level >= 3:
                gaps.append("证据仍为声明级，需通过的测试报告")
        shadows = sorted(set(shadow_by_code.get(code, [])))
        if shadows:
            gaps.append("疑似同一能力：" + "；".join(shadows)
                        + " 仅编码写法不同，人工确认后统一")
        art = artifact_paths(live or {})
        comparison.append({
            "code": code,
            "name": (plan or live or {}).get("name", code),
            "module": _short_module(code),
            "planned": bool(plan),
            "actual": bool(live),
            "status": status,
            "level": f"L{int(live.get('level', 0) or 0)}" if live else "L0",
            "target_level": target_level,
            "tier": live.get("evidence_tier", "declared") if live else "declared",
            "completion": live.get("completion", 0) if live else 0,
            "depends_on": list((plan or {}).get("depends_on", []) or []),
            "source_docs": [rel_path(x, target) for x in (plan or {}).get("sources", []) or []],
            "artifacts": {k: [rel_path(x, target) for x in v] for k, v in art.items()},
            "entry_ids": sorted({x.get("id") for x in ((live or {}).get("doc_index", {}) or {})
                                 .get("decisions", []) if isinstance(x, dict) and x.get("id")}),
            "commits": sorted(set(commits_by_code.get(code, []))),
            "shadow_match": shadows[0] if shadows else None,
            "shadow_matches": shadows,
            "alias_matches": sorted(set(alias_by_code.get(code, []))),
            "gaps": [g for g in gaps if g],
        })

    queue = cm.get("next_queue", []) or []
    queue_codes = {q.get("code") for q in queue}
    queue_items: list[dict] = []
    for item in queue:
        code = item.get("code", "")
        if code not in plan_by_code and plan_by_code:
            continue
        queue_items.append(item)

    # A 项：depends_on 的唯一消费点。仅在「同层」（同一 from→to 跃迁）内做稳定
    # 拓扑重排；depends_on 稀疏/全空时保持 next_queue 原序（等价当前行为）。
    dep_by_code = {code: [d for d in (plan.get("depends_on") or [])
                          if d in plan_by_code]
                   for code, plan in plan_by_code.items()}
    dep_cycles: list[list[str]] = []

    def _detect_cycles(codes: set[str]) -> list[list[str]]:
        color: dict[str, int] = {}
        found: list[list[str]] = []

        def visit(node: str, stack: list[str]) -> None:
            color[node] = 1
            stack.append(node)
            for nxt in dep_by_code.get(node, []):
                if nxt not in codes:
                    continue
                if color.get(nxt) == 1:
                    found.append(stack[stack.index(nxt):] + [nxt])
                elif color.get(nxt, 0) == 0:
                    visit(nxt, stack)
            stack.pop()
            color[node] = 2

        for code in sorted(codes):
            if color.get(code, 0) == 0:
                visit(code, [])
        return found

    dep_cycles = _detect_cycles(set(dep_by_code))
    if dep_cycles:
        # shadow 纪律：只告警，不改状态、不改退出码、不重排跨层顺序。
        shown = "；".join(" → ".join(c) for c in dep_cycles[:MAX_WARN_SHADOW_PAIRS])
        warnings.append(f"发现 {len(dep_cycles)} 组依赖环（仅提示，不影响队列顺序与状态）："
                        f"{shown}")

    layer_index: dict[str, int] = {}
    for index, item in enumerate(queue_items):
        key = (str(item.get("level", "L0")), str(item.get("target_level", "L5")))
        layer_index.setdefault(str(item.get("code", "")), index)
        item["_layer"] = key
        item["_index"] = index

    def _topo_sort(items: list[dict]) -> list[dict]:
        if not any(dep_by_code.get(str(i.get("code", ""))) for i in items):
            return items  # 全空：原序退化
        remaining = list(items)
        result: list[dict] = []
        done: set[str] = set()
        while remaining:
            ready = [i for i in remaining
                     if all(d in done or d not in {str(x.get("code", "")) for x in remaining}
                            for d in dep_by_code.get(str(i.get("code", "")), []))]
            if not ready:
                ready = remaining  # 环：保持原序，不卡死
            for item in ready:
                result.append(item)
                done.add(str(item.get("code", "")))
                remaining.remove(item)
        return result

    layers: dict[tuple, list[dict]] = {}
    for item in queue_items:
        layers.setdefault(item["_layer"], []).append(item)
    ordered_items: list[dict] = []
    for key in sorted(layers, key=lambda k: min(i["_index"] for i in layers[k])):
        ordered_items.extend(_topo_sort(layers[key]))

    execution_order: list[dict] = []
    for item in ordered_items:
        code = item.get("code", "")
        execution_order.append({
            "rank": len(execution_order) + 1,
            "code": code,
            "from": item.get("level", "L0"),
            "to": item.get("target_level", "L5"),
            "action": item.get("action", ""),
            "expert": "loop-executor",
            "preconditions": ["先跑 evidence-auditor 确认账本没坏"],
            "lessons": [x.get("id") for x in item.get("lessons", [])],
        })
    for row in comparison:
        if row["status"] in ("planned_only", "actual_only") and row["code"] not in queue_codes:
            if not plan_trustworthy:
                # 规划图不可信时不派 archaeologist 去「校准规划图」——
                # 根因是规划图本身缺失，应先跑生成器，而不是逐条伪校准。
                action = "先运行 architect_from_docs.py 生成有效目标规划图，再复核此条"
                expert = "loop-executor"
                preconditions = ["目标规划图缺失/不完整，漂移结论不可采信"]
            elif row["status"] == "actual_only":
                action = "先校准 registry 与证据路径，再补契约与测试"
                expert = "ledger-steward"
                preconditions = ["人工确认该能力是否应保留"]
            else:
                action = "先校准规划图与证据路径，再补契约与测试"
                expert = "project-archaeologist"
                preconditions = ["人工确认该能力是否应保留"]
            execution_order.append({
                "rank": len(execution_order) + 1,
                "code": row["code"],
                "from": row["level"],
                "to": row["target_level"],
                "action": action,
                "expert": expert,
                "preconditions": preconditions,
                "lessons": [],
            })

    overall = "ledger-steward"
    if route_build:
        try:
            routed = route_build(target, "校验账本并规划下一步", "auto", ".")
            overall = routed["route"]["expert"]
        except (OSError, ValueError, KeyError):
            pass

    summary = {status: sum(1 for r in comparison if r["status"] == status)
               for status in ("aligned", "in_progress", "not_started",
                              "planned_only", "actual_only")}
    summary.update({"planned": len(plan_by_code), "actual": len(actual_by_code),
                    "gaps": sum(1 for r in comparison if r["gaps"]),
                    "with_commits": sum(1 for r in comparison if r["commits"]),
                    "shadow_pairs": len(shadow_pairs)})
    return {
        "schema": "graph-diff/1",
        "plan_status": plan_status,
        "project": {
            "code": str(registry.get("project", {}).get("code", "PROJ")).upper(),
            "name": registry.get("project", {}).get("name", ""),
        },
        "sources": {
            "plan": plan_source,
            "actual": "DECISION_LEDGER.json / capability_model",
            "git": "GIT_TRACE.json" if git_trace else "未提供",
        },
        "modules": {
            "planned": [{"code": _short_module(str(m.get("code", ""))),
                         "name": m.get("name", "")} for m in planned_modules],
            "actual": [{"code": k, **v} for k, v in sorted(actual_modules.items())],
        },
        "comparison": comparison,
        "shadow_pairs": shadow_pairs,
        "dep_cycles": dep_cycles,
        "summary": summary,
        "execution_order": execution_order,
        "overall_expert": overall,
        "warnings": warnings,
    }


def render_report(diff: dict) -> str:
    s = diff["summary"]
    status = diff.get("plan_status", "present")
    if status != "present":
        lead = (f"# 规划图 vs 实际图 · 规划图{status}：本报告的漂移结论不可采信，"
                "先运行 architect_from_docs.py 生成有效规划图")
    else:
        lead = "# 规划图 vs 实际图"
    lines = [
        lead,
        "",
        f"> 规划来源：{diff['sources']['plan']}；实际来源：{diff['sources']['actual']}；"
        f"git：{diff['sources']['git']}。",
        "",
        f"对齐 {s['aligned']} / 进行中 {s['in_progress']} / 未启动 {s['not_started']} / "
        f"仅规划 {s['planned_only']} / 仅实际 {s['actual_only']} / "
        f"疑似同码 {s['shadow_pairs']}（仅提示）。",
        "",
        "## 能力比对",
        "",
        "| 编码 | 状态 | 实际→目标 | 分层 | 决策 | 提交 | 缺口 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in diff["comparison"]:
        lines.append(
            f"| {r['code']} | {r['status']} | {r['level']}→{r['target_level']} | {r['tier']} | "
            f"{', '.join(r['entry_ids']) or '—'} | {', '.join(r['commits']) or '—'} | "
            f"{'；'.join(r['gaps']) or '—'} |"
        )
    if diff.get("shadow_pairs"):
        lines.extend(["", "## 疑似同一能力", "",
                      "> 含格式变体与同义异码（alias_suspect，impl 路径相同/交集）；"
                      "状态与专家分派仍按字面码，须人工确认后统一。", "",
                      "| 归一键/类型 | 规划码 | 实际码 | 证据 |", "|---|---|---|---|"])
        for pair in diff["shadow_pairs"]:
            key = pair.get("canonical") or pair.get("kind", "")
            evidence = "、".join(pair.get("impl", [])) or "码写法归一"
            lines.append(f"| {key} | {pair['planned']} | {pair['actual']} | {evidence} |")
    lines.extend(["", "## 开发顺序（专家规划）", "",
                  "| 序 | 编码 | 跃迁 | 动作 | 专家 | 前置 |", "|---|---|---|---|---|---|"])
    for e in diff["execution_order"]:
        lines.append(f"| {e['rank']} | {e['code']} | {e['from']}→{e['to']} | {e['action']} | "
                     f"{e['expert']} | {'；'.join(e['preconditions']) or '—'} |")
    lines.extend(["", f"总负责人（路由建议）：{diff['overall_expert']}", ""])
    if diff["warnings"]:
        lines.extend(["## 警告", ""] + [f"- {w}" for w in diff["warnings"]] + [""])
    lines.extend(["## 关联", "", "- `governance/CODE_INDEX.json`：编码 ↔ artifact 全链路索引；",
                  "- `governance/GIT_TRACE.json`：提交 ↔ 能力/决策/事件映射。", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default=".", help="项目根目录")
    ap.add_argument("--target-arch", help="目标架构 JSON（默认 governance/TARGET_ARCHITECTURE.json）")
    ap.add_argument("--registry", help="registry.json 路径")
    ap.add_argument("--ledger", help="账本路径")
    ap.add_argument("--git-trace", help="GIT_TRACE.json 路径（可选）")
    ap.add_argument("--out", help="GRAPH_DIFF.json 输出路径")
    ap.add_argument("--report", help="GRAPH_DIFF.md 输出路径")
    ap.add_argument("--force", action="store_true", help="覆盖既有产物")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    target = Path(args.target).expanduser().resolve()
    gov = target / "governance"
    reg_path = Path(args.registry).expanduser().resolve() if args.registry else gov / "registry.json"
    led_path = Path(args.ledger).expanduser().resolve() if args.ledger else gov / "DECISION_LEDGER.json"
    if not reg_path.exists():
        print(f"缺少 registry：{reg_path}", file=sys.stderr)
        return 2
    registry = load_json(reg_path, "registry")
    ledger = load_json(led_path, "账本") if led_path.exists() else {}
    arch_path = Path(args.target_arch).expanduser().resolve() if args.target_arch else gov / "TARGET_ARCHITECTURE.json"
    target_arch = load_json(arch_path, "目标架构") if arch_path.exists() else None
    git_trace = {}
    if args.git_trace:
        gp = Path(args.git_trace).expanduser().resolve()
        if gp.exists():
            git_trace = load_json(gp, "git 追踪")

    diff = build(target, registry, ledger, target_arch, git_trace)
    report = render_report(diff)
    out = Path(args.out).expanduser().resolve() if args.out else gov / "GRAPH_DIFF.json"
    rep = Path(args.report).expanduser().resolve() if args.report else target / "docs" / "generated" / "GRAPH_DIFF.md"
    statuses = {}
    if not args.dry_run:
        statuses["json"] = write_if_absent(out, json.dumps(diff, ensure_ascii=False, indent=2) + "\n",
                                           args.force)
        statuses["report"] = write_if_absent(rep, report, args.force)
        if not args.json:
            print(f"[{statuses['json']}] {out}\n[{statuses['report']}] {rep}")
    if args.json or args.dry_run:
        print(json.dumps(diff, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
