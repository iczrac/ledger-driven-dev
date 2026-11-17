#!/usr/bin/env python3
"""从 registry + 账本重建规范化项目文档（单一事实源 → 文档）。

第一性原理：文档不该靠人肉同步。把「目标 / 模块 / 能力编码」从可机读事实源重新渲染，
人只维护 registry 与账本，生成文档始终与证据一致。默认不覆盖既有文件。

产物（默认 <target>/docs/generated/）：
    PROJECT_BRIEF.md      目标、范围、边界、状态词
    MODULE_MAP.md         模块 → 目录 → 能力编码
    CAPABILITY_INDEX.md   能力编码 → 文档 / 测试 / 代码 / 决策

用法：
    python3 scripts/rebuild_docs.py --target /path/to/project --dry-run
    python3 scripts/rebuild_docs.py --target /path/to/project
    python3 scripts/rebuild_docs.py --target . --force --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from trace_common import artifact_paths, iter_caps, load_json, rel_path, write_if_absent


def build_docs(target: Path, registry: dict, ledger: dict) -> dict[str, str]:
    code = str(registry.get("project", {}).get("code", "PROJ")).upper()
    name = registry.get("project", {}).get("name", code)
    caps = iter_caps(registry, ledger)
    modules = registry.get("modules", [])
    cm = ledger.get("capability_model", {})
    summary = cm.get("summary", {}) or {}
    completion = summary.get("overall_completion", "")
    level_dist = summary.get("level_distribution", {}) or {}

    goals = [
        f"覆盖 {len(modules)} 个模块、{len(caps)} 个能力点，能力编码为唯一身份证。",
        "完成度只能由真实证据派生；证据消失则等级回落。",
        "每个能力点都能对应到文档、测试、实现代码与账本决策。",
    ]
    brief = [
        f"# PROJECT_BRIEF · {code} {name}",
        "",
        "> 本文件由 `scripts/rebuild_docs.py` 从 registry 与账本重建。"
        "请勿手改；修改事实源后重新生成。",
        "",
        "## 为什么",
        "",
        str(ledger.get("purpose", "让决策、能力与证据收敛到单一事实源。")),
        "",
        "## 目标",
        "",
        *(f"- {g}" for g in goals),
        "",
        "## 现状（由账本派生）",
        "",
        f"- 整体完成度：{completion if completion != '' else '尚未生成'}",
        f"- 等级分布：{json.dumps(level_dist, ensure_ascii=False, sort_keys=True) if level_dist else '尚未生成'}",
        f"- 决策数：{len(ledger.get('entries', []))}",
        "",
        "## 边界 / 状态词",
        "",
        "- 决策：`proposed` / `decided` / `done` / `deferred` / `superseded`；",
        "- 成熟度：`L0` 规划 → `L1` 契约 → `L2` 实现 → `L3` 单测 → `L4` 运行验证 → `L5` 生产闭环；",
        "- 证据分层：`declared`（文件存在）/ `verified`（有通过的测试报告）。",
        "",
        "## 关联",
        "",
        "- `governance/registry.json`：唯一手写清单；",
        "- `governance/DECISION_LEDGER.json`：决策、历史、经验与能力派生结果；",
        "- `docs/generated/CAPABILITY_INDEX.md`：编码 ↔ 证据对应表。",
        "",
    ]

    module_lines = [
        f"# MODULE_MAP · {code}",
        "",
        "> 由单一事实源重建；`src` 是组件树扫描入口。",
        "",
        "## 模块与能力编码",
        "",
        "| 模块 | 名称 | 扫描入口 | 能力编码 |",
        "|---|---|---|---|",
    ]
    for mod in modules:
        mcode = str(mod.get("code", "CORE")).upper()
        mine = [c["code"] for c in caps if c["module_code"] == mcode]
        src = ", ".join(mod.get("src", []) or []) or "（无）"
        module_lines.append(f"| {mcode} | {mod.get('name', mcode)} | {src} | {', '.join(mine) or '（无）'} |")
    module_lines.extend(["", "## 边界", "", "- 模块边界来自 registry `modules[].src`，不是自动猜测；", "- 架构树由生成器从真实目录重算。", ""])

    cap_lines = [
        f"# CAPABILITY_INDEX · {code}",
        "",
        "> 每个编码对应文档 / 测试 / 代码 / 账本决策；路径相对项目根。",
        "",
        "| 编码 | 等级 | 证据 | 文档 | 测试 | 代码 | 决策 |",
        "|---|---|---|---|---|---|---|",
    ]
    for cap in caps:
        art = artifact_paths(cap)
        def cell(items: list[str]) -> str:
            cleaned = [rel_path(x, target) for x in items]
            return ", ".join(f"`{x}`" for x in cleaned) if cleaned else "—"
        cap_lines.append(
            f"| {cap['code']} | L{cap['level']}/{cap['tier']} | {cap['name']} | "
            f"{cell(art['docs'])} | {cell(art['tests'])} | {cell(art['code'])} | "
            f"{', '.join(cap['entry_ids']) or '—'} |"
        )
    cap_lines.extend([
        "",
        "## 关联",
        "",
        "- `governance/CODE_INDEX.json`：机器可读编码索引（含 git 提交映射）；",
        "- `docs/STANDARD.md`：命名、状态词与更新触发点。",
        "",
    ])

    return {
        "PROJECT_BRIEF.md": "\n".join(brief),
        "MODULE_MAP.md": "\n".join(module_lines),
        "CAPABILITY_INDEX.md": "\n".join(cap_lines),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default=".", help="项目根目录")
    ap.add_argument("--out-dir", help="文档输出目录（默认 <target>/docs/generated）")
    ap.add_argument("--force", action="store_true", help="覆盖已存在文档")
    ap.add_argument("--dry-run", action="store_true", help="只打印摘要，不写文件")
    ap.add_argument("--json", action="store_true", help="输出机器可读摘要")
    args = ap.parse_args(argv)

    target = Path(args.target).expanduser().resolve()
    gov = target / "governance"
    if not (gov / "registry.json").exists():
        print("缺少 governance/registry.json", file=sys.stderr)
        return 2
    registry = load_json(gov / "registry.json", "registry")
    ledger_path = gov / "DECISION_LEDGER.json"
    ledger = load_json(ledger_path, "账本") if ledger_path.exists() else {}
    docs = build_docs(target, registry, ledger)
    out = Path(args.out_dir).expanduser().resolve() if args.out_dir else target / "docs" / "generated"

    statuses = {}
    for name, content in docs.items():
        path = out / name
        statuses[name] = "dry-run" if args.dry_run else write_if_absent(path, content, args.force)
        if not args.dry_run and args.json is False:
            print(f"[{statuses[name]}] {path}")

    summary = {"schema": "doc-rebuild/1", "out_dir": rel_path(out, target),
               "files": statuses, "capabilities": len(iter_caps(registry, ledger))}
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    elif args.dry_run:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        print("\n--- 预览 PROJECT_BRIEF.md ---\n" + docs["PROJECT_BRIEF.md"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
