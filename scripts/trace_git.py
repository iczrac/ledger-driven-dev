#!/usr/bin/env python3
"""Git 更新 → 模块 / 能力 / 决策 / 历史事件的可追踪映射（只读）。

不做"提交信息里写了什么就信什么"：以 git log 的真实变更路径为证据，
再用 registry 与账本把路径对齐到能力编码、决策 id 与历史 seq。

用法：
    python3 scripts/trace_git.py --target /path/to/project --dry-run
    python3 scripts/trace_git.py --target /path/to/project --since 2026-11-01 --max-count 50
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from trace_common import artifact_paths, iter_caps, load_json, rel_path, write_if_absent


def _git_log(target: Path, since: str, max_count: int) -> list[dict]:
    cmd = ["git", "-C", str(target), "log", "--no-merges", "--name-only",
           "--date=short", "--format=COMMIT:%h|%ad|%s", "-n", str(max_count)]
    if since:
        cmd.append(f"--since={since}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"git log 失败：{proc.stderr.strip()}")
    commits: list[dict] = []
    current: dict | None = None
    for raw in proc.stdout.splitlines():
        if raw.startswith("COMMIT:"):
            parts = raw[len("COMMIT:"):].split("|", 2)
            if len(parts) != 3:
                continue
            current = {"hash": parts[0], "date": parts[1], "subject": parts[2], "paths": []}
            commits.append(current)
        elif current is not None and raw.strip():
            path = raw.strip()
            if path not in current["paths"]:
                current["paths"].append(path)
    return commits


def _matched(paths: list[str], declared: str) -> bool:
    d = declared.strip("/")
    if not d:
        return False
    for p in paths:
        if p == d:
            return True
        if d.endswith("/") and p.startswith(d):
            return True
        if Path(d).name == Path(p).name and Path(p).parent.as_posix().endswith(Path(d).parent.as_posix()):
            return True
    return False


def build(target: Path, registry: dict, ledger: dict, commits: list[dict]) -> dict:
    caps = iter_caps(registry, ledger)
    path_caps: dict[str, list[str]] = {}
    for cap in caps:
        art = artifact_paths(cap)
        declared = list(dict.fromkeys(art["docs"] + art["tests"] + art["code"]
                                      + art["impl_declared"] + cap["hints"]))
        for d in declared:
            if d.strip():
                path_caps.setdefault(rel_path(d, target), [])
                path_caps.setdefault(d, [])
                for key in (rel_path(d, target), d):
                    if cap["code"] not in path_caps[key]:
                        path_caps[key].append(cap["code"])

    module_src: dict[str, list[str]] = {}
    for m in registry.get("modules", []):
        for src in m.get("src", []) or []:
            module_src.setdefault(rel_path(src, target), []).append(str(m.get("code", "")).upper())

    entries = ledger.get("entries", [])
    events = (ledger.get("history") or {}).get("events", [])
    rows: list[dict] = []
    for commit in commits:
        paths = [rel_path(p, target) for p in commit["paths"]]
        cap_codes = sorted({c for p in paths for c in path_caps.get(p, [])})
        module_hits: set[str] = set()
        for p in paths:
            for src, mcodes in module_src.items():
                base = src.rstrip("/")
                if base in ("", ".") or p == base or p.startswith(base + "/") \
                        or Path(p).parent.as_posix() == base:
                    module_hits.update(mcodes)
        modules = sorted(module_hits)
        entry_ids = sorted({
            e.get("id", "") for e in entries
            if e.get("id") and any(
                p in " ".join(str(x) for x in e.get("evidence", [])) for p in paths
            )
        })
        event_seqs: list[int] = []
        signals: list[str] = []
        for ev in events:
            blob = json.dumps(ev.get("changes", {}), ensure_ascii=False)
            if any(code in blob for code in cap_codes) or any(p in blob for p in paths):
                seq = int(ev.get("seq", 0))
                if seq:
                    event_seqs.append(seq)
                for tr in (ev.get("changes") or {}).get("level_transitions", []):
                    if tr.get("code") in cap_codes:
                        signals.append(f"{tr['code']} {tr.get('from')}→{tr.get('to')}")
        if not cap_codes and not entry_ids and paths:
            signals.append("路径变更未命中能力编码（请校准 registry impl/hints）")
        rows.append({
            **{k: commit[k] for k in ("hash", "date", "subject")},
            "paths": paths,
            "modules": sorted(set(modules)),
            "cap_codes": cap_codes,
            "entry_ids": entry_ids,
            "event_seqs": sorted(set(event_seqs)),
            "iteration_signals": sorted(set(signals)),
        })
    return {
        "schema": "git-trace/1",
        "source": "git log (read-only)",
        "commits": rows,
        "summary": {
            "commits": len(rows),
            "mapped_commits": sum(1 for r in rows if r["cap_codes"] or r["entry_ids"] or r["event_seqs"]),
            "capabilities_touched": len({c for r in rows for c in r["cap_codes"]}),
            "decisions_touched": len({d for r in rows for d in r["entry_ids"]}),
            "events_touched": len({s for r in rows for s in r["event_seqs"]}),
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default=".", help="项目根目录（需为 git 仓库）")
    ap.add_argument("--since", default="", help="git log --since 参数，如 2026-11-01")
    ap.add_argument("--max-count", type=int, default=30, help="最多读取多少条提交")
    ap.add_argument("--out", help="输出路径（默认 <target>/governance/GIT_TRACE.json）")
    ap.add_argument("--force", action="store_true", help="覆盖既有追踪结果")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    target = Path(args.target).expanduser().resolve()
    if not (target / ".git").exists():
        print(f"目标不是 git 仓库：{args.target}", file=sys.stderr)
        return 2
    gov = target / "governance"
    reg_path = gov / "registry.json"
    if not reg_path.exists():
        print("缺少 governance/registry.json", file=sys.stderr)
        return 2
    registry = load_json(reg_path, "registry")
    ledger_path = gov / "DECISION_LEDGER.json"
    ledger = load_json(ledger_path, "账本") if ledger_path.exists() else {}
    commits = _git_log(target, args.since, args.max_count)
    result = build(target, registry, ledger, commits)
    out = Path(args.out).expanduser().resolve() if args.out else gov / "GIT_TRACE.json"

    if not args.dry_run:
        status = write_if_absent(out, json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                 args.force)
        if not args.json:
            print(f"[{status}] {out}")
    if args.json or args.dry_run:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        s = result["summary"]
        print(f"git 追踪：{s['commits']} 提交，命中能力 {s['capabilities_touched']}、"
              f"决策 {s['decisions_touched']}、事件 {s['events_touched']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
