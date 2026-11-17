#!/usr/bin/env python3
"""规范编码索引：一个能力编码对应文档 / 测试 / 代码 / 账本 / git 的全链路映射。

编码形如 `PROJ.MODULE.DOMAIN.NN`，是跨artifact的唯一身份证。本脚本把它展开成
机器可读索引，供看板、审计与 AI 任务卡消费；只读取证，不写账本。

用法：
    python3 scripts/code_index.py --target /path/to/project
    python3 scripts/code_index.py --target . --git-trace governance/GIT_TRACE.json --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from trace_common import artifact_paths, iter_caps, load_json, rel_path, write_if_absent


def _event_refs(ledger: dict, code: str) -> list[int]:
    refs: list[int] = []
    for ev in (ledger.get("history") or {}).get("events", []):
        blob = json.dumps(ev.get("changes", {}), ensure_ascii=False)
        if code in blob:
            refs.append(int(ev.get("seq", 0)))
    return sorted(set(x for x in refs if x))


def build_index(target: Path, registry: dict, ledger: dict, git_trace: dict) -> dict:
    commits_by_code: dict[str, list[str]] = {}
    for commit in git_trace.get("commits", []):
        for code in commit.get("cap_codes", []):
            commits_by_code.setdefault(code, []).append(commit.get("hash", ""))
    caps = iter_caps(registry, ledger)
    rows = []
    for cap in caps:
        art = artifact_paths(cap)
        art = {k: [rel_path(x, target) for x in v] for k, v in art.items()}
        rows.append({
            **{k: cap[k] for k in ("code", "module_code", "module_name", "domain",
                                   "name", "hints", "level", "tier", "next_action")},
            "artifacts": art,
            "entry_ids": cap["entry_ids"],
            "event_seqs": _event_refs(ledger, cap["code"]),
            "commits": sorted(set(commits_by_code.get(cap["code"], []))),
        })
    return {
        "schema": "code-index/1",
        "project": {
            "code": str(registry.get("project", {}).get("code", "PROJ")).upper(),
            "name": registry.get("project", {}).get("name", ""),
        },
        "caps": rows,
        "summary": {
            "capabilities": len(rows),
            "with_docs": sum(1 for r in rows if r["artifacts"]["docs"]),
            "with_tests": sum(1 for r in rows if r["artifacts"]["tests"]),
            "with_code": sum(1 for r in rows if r["artifacts"]["code"] or r["artifacts"]["impl_declared"]),
            "with_entries": sum(1 for r in rows if r["entry_ids"]),
            "with_commits": sum(1 for r in rows if r["commits"]),
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default=".", help="项目根目录")
    ap.add_argument("--git-trace", help="GIT_TRACE.json 路径（可选，补充 commit 映射）")
    ap.add_argument("--out", help="输出路径（默认 <target>/governance/CODE_INDEX.json）")
    ap.add_argument("--force", action="store_true", help="覆盖既有索引")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    target = Path(args.target).expanduser().resolve()
    gov = target / "governance"
    if not (gov / "registry.json").exists():
        print("缺少 governance/registry.json", file=sys.stderr)
        return 2
    registry = load_json(gov / "registry.json", "registry")
    ledger_path = gov / "DECISION_LEDGER.json"
    ledger = load_json(ledger_path, "账本") if ledger_path.exists() else {}
    git_trace = {}
    if args.git_trace:
        gp = Path(args.git_trace).expanduser().resolve()
        if gp.exists():
            git_trace = load_json(gp, "git 追踪")
        else:
            print(f"[WARN] git 追踪文件不存在，commit 映射为空：{gp}", file=sys.stderr)

    index = build_index(target, registry, ledger, git_trace)
    out = Path(args.out).expanduser().resolve() if args.out else gov / "CODE_INDEX.json"
    if not args.dry_run:
        status = write_if_absent(out, json.dumps(index, ensure_ascii=False, indent=2) + "\n",
                                 args.force)
        if not args.json:
            print(f"[{status}] {out}")

    if args.json or args.dry_run:
        print(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
