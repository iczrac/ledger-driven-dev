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
    if target_arch:
        planned_caps = target_arch.get("capabilities", [])
        planned_modules = target_arch.get("modules", [])
        plan_source = "TARGET_ARCHITECTURE.json"
    else:
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
            "gaps": [g for g in gaps if g],
        })

    queue = cm.get("next_queue", []) or []
    queue_codes = {q.get("code") for q in queue}
    execution_order: list[dict] = []
    for item in queue:
        code = item.get("code", "")
        if code not in plan_by_code and plan_by_code:
            continue
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
            execution_order.append({
                "rank": len(execution_order) + 1,
                "code": row["code"],
                "from": row["level"],
                "to": row["target_level"],
                "action": "先校准规划图/registry 与证据路径，再补契约与测试",
                "expert": "ledger-steward" if row["status"] == "actual_only" else "project-archaeologist",
                "preconditions": ["人工确认该能力是否应保留"],
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
        "summary": summary,
        "execution_order": execution_order,
        "overall_expert": overall,
        "warnings": warnings,
    }


def render_report(diff: dict) -> str:
    s = diff["summary"]
    lines = [
        "# 规划图 vs 实际图",
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
                      "> 仅编码写法不同；状态与专家分派仍按字面码，须人工确认后统一。", "",
                      "| 归一键 | 规划码 | 实际码 |", "|---|---|---|"])
        for pair in diff["shadow_pairs"]:
            lines.append(f"| {pair['canonical']} | {pair['planned']} | {pair['actual']} |")
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
