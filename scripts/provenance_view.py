#!/usr/bin/env python3
"""来源投影 + 完成定义：把账本既有字段按 [AI推断]/[人确认] 分组展示，
并为任务卡从既有字段派生 definition_of_done。只读、可复算、不落盘。

第一性原理
----------
外部方法论值得借鉴的是「让 AI 产出与人确认可区分」，但**不是**往账本再加
一个 origin 字段——issue 早有 `source=derived` + `derived_from`（机器控制）
与 `owner/owner_note/detail`（人补、重算保留），decision 早有 `status:
proposed→done`。再落一个 `origin=ai-inferred` 就是同一事实两处表达，
违背单一事实源。

所以本脚本只做展示层投影，沿用 ontology.py / work_panel.py 的「只读投影」
范式：
  - 机器控制字段（[AI推断]）：手改会被重算覆盖，投影明确标出「勿手改」；
  - 人工字段（[人确认]）：重算保留，投影标出「人补」；
  - 完成定义从 target_level + missing_evidence 派生，不写回账本。

projection = f(账本)：同账本必得逐字节一致输出。不新增任何账本字段，
不改变任何不变量，不参与写入链——P2「不改治理规则」的纪律由此保证。

退出码：0 正常；1 账本不可读 / 结构非法；2 用法错误

用法
----
    python3 scripts/provenance_view.py --target P --json
    python3 scripts/provenance_view.py --target P --kind issue --json
    python3 scripts/provenance_view.py --target P --kind task --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCHEMA = "provenance-view/1"
LEDGER_REL = "governance/DECISION_LEDGER.json"

# 机器控制字段：由生成器/门禁写入，人手工修改会在重算时被覆盖。
ISSUE_MACHINE_FIELDS = (
    "id", "kind", "scope", "status", "severity", "source", "derived_from",
    "close_condition", "refs", "resolution", "auto_closed",
)
ISSUE_HUMAN_FIELDS = ("owner", "owner_note", "detail")
DECISION_MACHINE_FIELDS = ("id", "date", "status", "supersedes")
DECISION_HUMAN_FIELDS = ("title", "category", "scope", "decision", "rationale",
                         "evidence", "confidence")


def load_ledger(target: Path) -> dict:
    path = target / LEDGER_REL
    return json.loads(path.read_text(encoding="utf-8"))


def _pick(obj: dict, keys: tuple[str, ...]) -> dict:
    """只取存在的键，保持键顺序稳定（投影可复算）。"""
    return {k: obj[k] for k in keys if k in obj}


def _label(fields: dict, kind: str) -> dict:
    return {"label": kind, "fields": fields}


def issue_projection(item: dict) -> dict:
    """单个 issue 的来源分组。机器字段标「勿手改」，人工字段标「人补」。"""
    return {
        "id": item.get("id"),
        "scope": item.get("scope"),
        "status": item.get("status"),
        "ai_inferred": _label(_pick(item, ISSUE_MACHINE_FIELDS), "[AI推断] 机器控制，重算覆盖，勿手改"),
        "human_confirmed": _label(_pick(item, ISSUE_HUMAN_FIELDS), "[人确认] 人补充，重算保留"),
    }


def decision_projection(entry: dict) -> dict:
    """单个 decision 的来源分组：结构/流转由机器，内容由人拍板。"""
    return {
        "id": entry.get("id"),
        "status": entry.get("status"),
        "ai_inferred": _label(_pick(entry, DECISION_MACHINE_FIELDS),
                              "[AI推断] 结构与状态流转由生成器控制"),
        "human_confirmed": _label(_pick(entry, DECISION_HUMAN_FIELDS),
                                  "[人确认] 内容由人拍板，机器仅记录"),
    }


def definition_of_done(task: dict) -> dict:
    """从任务卡既有字段派生完成定义，不写回账本。

    - target_level：目标成熟度
    - criteria：缺失证据项（做到这些即达标）
    - machine_check：判定达标的可运行门禁
    - provenance：明确这是派生投影，不是账本字段
    """
    target_level = task.get("target_level")
    missing = list(task.get("missing_evidence") or [])
    return {
        "code": task.get("code"),
        "target_level": target_level,
        "criteria": missing,
        "machine_check": "python3 governance/build_capability_model.py --root . --check",
        "satisfied_when": ("missing_evidence 为空且 evidence_tier=verified"
                           "（v2.2.0 起 verified⟺bound）"),
        "provenance": "从 target_level + missing_evidence 派生；非账本字段，不写回",
    }


def project(ledger: dict, kind: str = "all") -> dict:
    """把账本投影成来源分组 + 完成定义。纯函数，不修改入参。"""
    out: dict = {
        "schema": SCHEMA,
        "source_ledger": LEDGER_REL,
        "note": "只读投影：不新增账本字段、不改变不变量、不参与写入链",
        "kind": kind,
    }
    if kind in ("all", "issue"):
        issues = [x for x in (ledger.get("work_items") or [])
                  if isinstance(x, dict) and x.get("kind") == "issue"]
        out["issues"] = [issue_projection(x) for x in issues]
    if kind in ("all", "decision"):
        entries = [x for x in (ledger.get("entries") or []) if isinstance(x, dict)]
        out["decisions"] = [decision_projection(x) for x in entries]
    if kind in ("all", "task"):
        tasks = [x for x in (ledger.get("capability_model", {}).get("next_queue") or [])
                 if isinstance(x, dict)]
        out["tasks"] = [definition_of_done(x) for x in tasks]
    counts = {k: len(out[k]) for k in ("issues", "decisions", "tasks") if k in out}
    out["summary"] = " · ".join(f"{k}={v}" for k, v in counts.items()) or "空投影"
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="来源投影 + 完成定义（只读，不写账本）")
    ap.add_argument("--target", default=".", help="目标项目根目录")
    ap.add_argument("--kind", choices=("all", "issue", "decision", "task"), default="all")
    ap.add_argument("--json", action="store_true", help="输出 JSON（默认人类可读摘要）")
    args = ap.parse_args(argv)
    try:
        ledger = load_ledger(Path(args.target))
    except (OSError, ValueError) as exc:
        print(f"账本不可读：{exc}", file=sys.stderr)
        return 1
    out = project(ledger, args.kind)
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"来源投影 → {out['summary']}")
        for key in ("issues", "decisions", "tasks"):
            for row in out.get(key, [])[:5]:
                label = row.get("id") or row.get("code")
                print(f"  [{key}] {label}")
        if out.get("tasks"):
            sample = out["tasks"][0]
            print(f"  示例完成定义：{sample['code']} → {sample['target_level']}"
                  f"，缺口 {sample['criteria']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
