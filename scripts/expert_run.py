#!/usr/bin/env python3
"""专家团自动编排器（expert-run）：把路由结果展开成可执行的分工与批准包。

第一性原理
----------
P0 让 ``route_expert`` 输出确定性负责人 + 多跳交接链 ``handoff.chain``，
但「把链变成行动」仍靠编排层人肉：读 EXPERT.md、挑命令、判断哪条要批准、
口头转达下一位专家。这是「全 AI 驱动」最大的断点。

expert-run 补的就是这一环，但它**没有任何新判定权**：
  - 负责人、置信度、交接链、建议命令，全部来自 ``route_expert.build``；
  - 专家契约（skills / writes / EXPERT.md 路径）来自同一份 ``EXPERT_CARDS``；
  - 本脚本只做两件事：①把建议命令分类成 readonly / approval / manual；
    ②沿交接链打包成一份「批准包」（approval bundle）。

它**默认 dry-run、零执行**：不跑任何命令、不写任何文件、不碰账本。
人拿到批准包后，只在带 ``--approved-by`` 的写入点逐条执行——
「权限授予者 ≠ 被授权者」这条铁律不被绕过。

可复算：run = f(intent, target, route_expert, EXPERT_CARDS, commands_for)；
同输入同版本必得逐字节一致输出。失败即 fail-closed（blocked / needs_clarification
时 chain 与批准包为空，只给 halt_reason）。

退出码：0=ready（可进入人工批准） 1=blocked/需澄清（fail-closed） 2=用法错误

用法
----
    python3 scripts/expert_run.py --target P --intent "校验账本" --json
    python3 scripts/expert_run.py --target P --intent-file intent.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import route_expert as route  # noqa: E402

SCHEMA = "expert-run/1"

# 命令分类：宁可保守归 approval，也绝不把可能是写的命令判成只读。
# 顺序即优先级：命中即停。
APPROVAL_TOKENS = (
    "--approved-by", "--apply", "register", "unfreeze", "archive", "freeze",
    "retire",
)
# 明确的只读动作标志：出现任一即视为只读（除非先命中 APPROVAL_TOKENS）。
READONLY_TOKENS = (
    "--dry-run", "--check", "--diff", "--json", "--help", "--strict",
    "verify_ledger.py", "verify", " status", " nodes", " report", " plan",
    "check.sh", "trace_git.py", "compare_graphs.py", "code_index.py",
    "method_assets.py", "test_modules.py", "asset_bundle.py --check",
    "asset_bundle.py manifest", "asset_bundle.py verify",
    "work_panel.py", "board_contract.py", "scale_budget.py",
    "route_expert.py", "intent_restate.py", "scenario_guard.py",
    "ontology.py", "ledger_guard.py", "acceptance.py", "upgrade.py check",
    "agent_gateway.py ... status", "agent_gateway.py status",
)
# 明确的写命令（无只读标志时归 approval，归入这里只为给出可读 reason）。
WRITE_COMMANDS = (
    "init_project.py", "discover_project.py", "architect_from_docs.py",
    "rebuild_docs.py", "build_capability_model.py", "upgrade.py",
    "agent_gateway.py", "lifecycle.py", "ledger_decide.py", "ledger_lesson.py",
)


def classify_command(command: str) -> dict:
    """把一条建议命令分类为 readonly / approval / manual。

    保守原则（fail-closed）：任何含写授权或写动词、且没有明确只读标志的
    命令，一律归 approval，不自动执行。本函数不判定业务对错，只做文本分类。
    """
    cmd = command.strip()
    for tok in APPROVAL_TOKENS:
        if tok in cmd:
            return {"class": "approval",
                    "reason": f"含写授权动作 {tok.strip()}：须人 --approved-by 后执行"}
    for tok in READONLY_TOKENS:
        if tok in cmd:
            return {"class": "readonly", "reason": f"只读动作 {tok.strip()}：可直接执行"}
    for tok in WRITE_COMMANDS:
        if tok in cmd:
            return {"class": "approval",
                    "reason": f"写命令 {tok} 且无只读标志：须人批准"}
    return {"class": "manual", "reason": "无法判定：默认交人工，不自动执行"}


def _halt(route_result: dict, intent: str, display: str) -> dict:
    """fail-closed：路由未通过时，chain 与批准包为空，只给停止原因。"""
    clarification = route_result.get("needs_clarification")
    verdict = ("needs_clarification" if clarification else
               "blocked" if route_result["route"].get("blocked") else "halted")
    reason = (str(clarification.get("question") if isinstance(clarification, dict)
                  else clarification) if clarification else
              str(route_result["route"].get("reason", "路由未就绪")))
    return {
        "schema": SCHEMA, "target": display, "intent": intent, "mode": "dry-run",
        "verdict": verdict, "halt_reason": reason, "chain": [],
        "approval_bundle": {"commands": [], "count": 0,
                            "note": "路由未通过，不生成可批准动作"},
        "summary": "fail-closed：先消除澄清/阻塞再编排",
    }


def _step(index: int, expert: str, chain: list[str], display: str) -> dict:
    """把一个专家展开成契约 + 分类命令 + 下一步交接。

    display 透传给 commands_for，保证批准包里的命令携带真实 target，
    人复制即可执行，而不是硬编码的占位符。
    """
    card = route.EXPERT_CARDS.get(expert, {})
    commands = route.commands_for(expert, display)
    classified = [dict(command=c, **classify_command(c)) for c in commands]
    approvals = [c["command"] for c in classified if c["class"] == "approval"]
    next_expert = chain[index + 1] if index + 1 < len(chain) else None
    return {
        "index": index,
        "expert": expert,
        "title": card.get("title", expert),
        "duty": card.get("duty", ""),
        "contract": {
            "expert_md": f"experts/{expert}/EXPERT.md",
            "skills": list(card.get("skills", [])),
            "writes": list(card.get("writes", [])),
        },
        "commands": classified,
        "readonly_count": sum(1 for c in classified if c["class"] == "readonly"),
        "approval_count": len(approvals),
        "next_expert": next_expert,
    }


def run(target: Path, intent: str, intent_file: str | None = None,
        display: str | None = None) -> dict:
    """纯只读编排：从路由结果展开交接链，产出批准包，不执行任何命令。"""
    display = display or str(target)
    route_result = route.build(target, intent, "auto", display)
    r = route_result["route"]
    if r.get("blocked") or route_result.get("needs_clarification"):
        out = _halt(route_result, intent, display)
    else:
        chain = list(r.get("handoff", {}).get("chain") or [r["expert"]])
        steps = [_step(i, e, chain, display) for i, e in enumerate(chain)]
        bundle = [{"step": s["index"], "expert": s["expert"], "command": c["command"],
                   "reason": c["reason"]}
                  for s in steps for c in s["commands"] if c["class"] == "approval"]
        out = {
            "schema": SCHEMA, "target": display, "intent": intent, "mode": "dry-run",
            "verdict": "ready",
            "route": {
                "expert": r["expert"], "confidence": r["confidence"],
                "detected_mode": route_result.get("detected_mode"),
                "intents": route_result.get("intents", []),
            },
            "chain": steps,
            "approval_bundle": {
                "commands": bundle, "count": len(bundle),
                "note": "仅在这些点由人批准执行；expert-run 不代跑、不写账本",
            },
            "summary": (f"交接链 {len(steps)} 跳，只读命令 "
                        f"{sum(s['readonly_count'] for s in steps)} 条，"
                        f"需批准 {len(bundle)} 条"),
        }
    if intent_file:
        out["restate_source"] = intent_file
    return out


def render(out: dict) -> str:
    """人类可读摘要：链 + 每跳契约 + 批准点。"""
    lines = [f"编排 → {out['verdict']}｜{out.get('summary', out.get('halt_reason', ''))}"]
    if out.get("halt_reason"):
        lines.append(f"停止原因：{out['halt_reason']}")
        return "\n".join(lines)
    for s in out["chain"]:
        lines.append(
            f"[{s['index']}] {s['expert']}（{s['title']}）"
            f"｜技能 {len(s['contract']['skills'])} 项"
            f"｜写范围 {','.join(s['contract']['writes']) or '无'}"
            f"｜只读 {s['readonly_count']} / 批准 {s['approval_count']}"
        )
        nxt = f" → 交接 {s['next_expert']}" if s["next_expert"] else " → 终点"
        lines.append(f"    {nxt}；契约见 {s['contract']['expert_md']}")
    b = out["approval_bundle"]
    lines.append(f"批准包：{b['count']} 条写入命令（人批准后逐条执行）")
    for c in b["commands"][:8]:
        lines.append(f"    - [{c['expert']}] {c['command']}")
    if b["count"] > 8:
        lines.append(f"    ... 另有 {b['count'] - 8} 条，见 JSON")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="专家团自动编排器（dry-run，零执行）")
    ap.add_argument("--target", default=".", help="目标项目根目录")
    ap.add_argument("--intent", default="", help="本轮意图的自然语言描述")
    ap.add_argument("--intent-file", help="复述门结构化意图声明（可选，仅记录来源）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)
    out = run(Path(args.target), args.intent, args.intent_file)
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render(out))
    return 0 if out["verdict"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
