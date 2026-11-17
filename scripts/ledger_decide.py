#!/usr/bin/env python3
"""从 next_queue 生成一条 proposed 决策写入账本。

纪律由代码保证：目标必须在任务队列中、同一能力不得重复立项、只写 proposed、
不改能力状态、不手改完成度。仅供 ledger-decide skill 调用。
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

OPEN_STATUS = {"proposed", "decided"}


def next_id(entries: list[dict]) -> str:
    nums = [
        int(m.group(1)) for e in entries
        if (m := re.match(r"^D-(\d+)$", str(e.get("id", ""))))
    ]
    return f"D-{max(nums, default=0) + 1:03d}"


def decide(ledger: dict, code: str, title: str, rationale: str,
           category: str = "能力建设", scope: str | None = None,
           confidence: str = "medium") -> dict:
    """写入一条 proposed 决策；失败抛 ValueError，账本不变。"""
    tasks = ledger.get("capability_model", {}).get("next_queue", [])
    task = next((t for t in tasks if t.get("code") == code), None)
    if task is None:
        raise ValueError(f"能力 {code} 不在 next_queue；请先重跑生成器确认它未完成")
    if not title or not rationale:
        raise ValueError("title 与 rationale 不得为空")

    entries = ledger.setdefault("entries", [])
    conflict = [
        e.get("id") for e in entries
        if code in (e.get("evidence") or [])
        and e.get("status") in OPEN_STATUS
    ]
    if conflict:
        raise ValueError(f"能力 {code} 已有未结决策 {conflict}，不得重复立项")

    docs = task.get("docs", {})
    evidence = [code] + [p for k in ("plans", "impl", "unit_tests")
                         for p in docs.get(k, [])][:2]
    entry = {
        "id": next_id(entries),
        "date": date.today().isoformat(),
        "title": title,
        "category": category,
        "scope": scope or task.get("project", ""),
        "status": "proposed",
        "supersedes": None,
        "decision": f"{title}：{task.get('action', '')}",
        "rationale": rationale,
        "evidence": evidence,
        "confidence": confidence,
    }
    entries.append(entry)
    return entry


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ledger", required=True, help="DECISION_LEDGER.json 路径")
    ap.add_argument("--code", required=True, help="next_queue 中的能力编码")
    ap.add_argument("--title", required=True, help="决策标题")
    ap.add_argument("--rationale", required=True, help="为什么现在做，引用证据")
    ap.add_argument("--category", default="能力建设")
    ap.add_argument("--scope", help="项目代码；默认取任务卡的 project")
    ap.add_argument("--confidence", default="medium", choices=["high", "medium", "low"])
    args = ap.parse_args()

    path = Path(args.ledger)
    ledger = json.loads(path.read_text())
    try:
        entry = decide(ledger, args.code, args.title, args.rationale,
                       args.category, args.scope, args.confidence)
    except ValueError as exc:
        raise SystemExit(f"拒绝写入：{exc}")
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2))
    print(f"已写入 {entry['id']} proposed → {args.code}")
    print("下一步：执行证据补齐后重跑生成器，达标再把状态流转为 done。")


if __name__ == "__main__":
    main()
