#!/usr/bin/env python3
"""把 lessons.candidates 确认成经验条目，或写明理由驳回。

纪律由代码保证：候选必须存在、confirmed 必须有 insight 与 action、
驳回必须给理由。确认后须重跑生成器，任务卡才会携带新经验。
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path


def next_id(items: list[dict]) -> str:
    nums = [
        int(m.group(1)) for x in items
        if (m := re.match(r"^L-(\d+)$", str(x.get("id", ""))))
    ]
    return f"L-{max(nums, default=0) + 1:03d}"


def _find(lessons: dict, cand_id: str) -> dict:
    cand = next((c for c in lessons.get("candidates", []) if c.get("id") == cand_id), None)
    if cand is None:
        raise ValueError(f"候选 {cand_id} 不存在；请先重跑生成器刷新候选")
    return cand


def confirm_lesson(ledger: dict, cand_id: str, title: str,
                   insight: str, action: str, scope: dict | None = None) -> dict:
    if not insight or not action:
        raise ValueError("confirmed 经验必须同时提供 insight（为什么）与 action（下次怎么做）")
    lessons = ledger.setdefault("lessons", {"spec": {}, "items": [], "candidates": []})
    cand = _find(lessons, cand_id)
    items = lessons.setdefault("items", [])
    item = {
        "id": next_id(items),
        "status": "confirmed",
        "created_ts": datetime.now().strftime("%Y-%m-%d %H:%M HKT"),
        "title": title,
        "insight": insight,
        "action": action,
        "scope": scope if scope is not None else dict(cand.get("suggested_scope") or {}),
        "source_events": list(cand.get("source_events") or []),
        "from_candidate": cand_id,
    }
    items.append(item)
    return item


def dismiss_lesson(ledger: dict, cand_id: str, reason: str) -> dict:
    if not reason:
        raise ValueError("驳回候选必须写明理由，否则同一信号会反复打扰")
    lessons = ledger.setdefault("lessons", {"spec": {}, "items": [], "candidates": []})
    cand = _find(lessons, cand_id)
    cand["status"] = "dismissed"
    cand["dismiss_reason"] = reason
    return cand


def scope_from_args(args) -> dict | None:
    parts = {
        "capabilities": args.scope_capabilities,
        "projects": args.scope_projects,
        "domains": args.scope_domains,
        "levels": args.scope_levels,
    }
    result = {
        k: [x.strip() for x in v.split(",") if x.strip()]
        for k, v in parts.items() if v
    }
    return result or None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--candidate", required=True, help="候选 id，如 LC-C1CDBB")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--confirm", action="store_true", help="确认成经验条目")
    group.add_argument("--dismiss", action="store_true", help="驳回候选")
    ap.add_argument("--title")
    ap.add_argument("--insight")
    ap.add_argument("--action")
    ap.add_argument("--reason")
    ap.add_argument("--scope-capabilities")
    ap.add_argument("--scope-projects")
    ap.add_argument("--scope-domains")
    ap.add_argument("--scope-levels")
    args = ap.parse_args()

    path = Path(args.ledger)
    ledger = json.loads(path.read_text())
    try:
        if args.confirm:
            if not args.title:
                raise ValueError("确认经验需要 --title")
            item = confirm_lesson(ledger, args.candidate, args.title,
                                  args.insight or "", args.action or "",
                                  scope_from_args(args))
            message = f"已确认 {item['id']} ← {args.candidate}（scope={item['scope']}）"
        else:
            dismiss_lesson(ledger, args.candidate, args.reason or "")
            message = f"已驳回 {args.candidate}"
    except ValueError as exc:
        raise SystemExit(f"拒绝写入：{exc}")

    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2))
    print(message)
    print("下一步：重跑生成器让任务卡携带新经验，再做 verify --strict。")


if __name__ == "__main__":
    main()
