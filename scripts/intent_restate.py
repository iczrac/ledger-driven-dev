#!/usr/bin/env python3
"""复述门（intent-restate）：把人话意图变成结构化声明，再用真实 registry/账本校验。

为什么需要这一层
----------------
route_expert.py 会把「让专家团接管全流程」这类编排指令判成 intents=[]，
然后照常路由——意图没被听懂，机器却往下走了。复述门补上「人话 → 复述
确认 → 意图 → 路由」之间缺的一环：Agent 先用结构化 JSON 声明它理解的
目标、涉及能力与写入范围，机器再校验这些声明能否锚定回真实证据。

设计原则（对齐项目第一性原理）：
- 声明权 ≠ 伪造权：Agent 的复述只是「声明」，必须机器校验能映射回真实
  证据才放行；幻觉能力码、只读意图越权写入都会被拒。
- 可复算：gate 结论 = f(intent.json, registry, ledger)；同输入必得同输出。
- fail-closed：任何字段无法锚定到真实条目 -> need_clarification / reject，
  不让路由继续。
- 不写盘：本脚本纯只读，不修改 registry/账本/源码。

接入方式
--------
1. 独立 CLI：python3 scripts/intent_restate.py --target P --intent-file I --json
2. 路由前置：route_expert.py 在 --intent-file 存在时先跑本门，非 allow 即
   把结论并入 needs_clarification，不让模糊意图静默进入路由。

退出码：0=allow（可进入路由） 1=need_clarification（复述不清，抛回人）
        2=reject（锚定失败/幻觉） 3=用法错误
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCHEMA = "intent-restate/0"

# 合法意图分类（对齐 route_expert.INTENT_PATTERNS 的 key）
VALID_INTENTS = {
    "new", "adopt", "verify", "plan", "code", "lesson", "route",
    "archive", "migrate", "access", "retire", "resume", "doc",
    "meta",  # 编排类元指令：不指向具体能力，如"让专家团接管全流程"
}

# 合法写入范围（对齐 EXPERT_CARDS.writes 的并集 + 只读）
VALID_SCOPES = {
    "none", "entries", "lessons.items", "src/**", "tests/**",
    "docs/test_records/**", "governance/registry.json",
    "governance/DECISION_LEDGER.json", "lifecycle", "retired_caps",
    "governance_meta", "access", "docs.registry", "docs.obligations",
}


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def collect_cap_codes(registry: dict, ledger: dict) -> set[str]:
    """从 registry 与账本 capability_model 收集全部真实能力 code。"""
    codes: set[str] = set()
    # capability_model.projects[].modules[].caps[].code
    cm = ledger.get("capability_model", {})
    for proj in cm.get("projects", []):
        for mod in proj.get("modules", []):
            for cap in mod.get("caps", []):
                if cap.get("code"):
                    codes.add(cap["code"])
    # next_queue 也是真实能力引用
    for item in cm.get("next_queue", []):
        if item.get("code"):
            codes.add(item["code"])
    # work_items 的 scope 引用
    for wi in ledger.get("work_items", []):
        sc = wi.get("scope")
        if sc:
            codes.add(sc)
    return codes


def validate(intent: dict, registry: dict, ledger: dict) -> dict:
    """纯函数：intent + 真实证据 -> 复述门结论。"""
    checks: list[dict] = []

    def add(cid: str, status: str, reason: str, fix: str = "") -> None:
        checks.append({"id": cid, "status": status, "reason": reason, "fix": fix})

    # 1. schema 契约
    if intent.get("schema") != SCHEMA:
        add("schema", "reject", f"schema 应为 {SCHEMA}，实为 {intent.get('schema')!r}",
            "按模板重生成 intent.json")
    else:
        add("schema", "pass", "schema 合规")

    # 2. 复述不是原话照抄，且非空
    raw = (intent.get("raw_intent") or "").strip()
    restate = (intent.get("restatement") or "").strip()
    if not raw or not restate:
        add("restate_nonempty", "reject", "raw_intent 或 restatement 为空", "补齐两字段")
    elif restate == raw:
        add("restate_nonempty", "need_clarification", "复述与原话逐字相同，未产生理解增量",
            "用自己的话复述底层目标，不要复制原话")
    else:
        add("restate_nonempty", "pass", "复述有理解增量")

    # 3. 意图分类合法
    intents = intent.get("intents") or []
    if not isinstance(intents, list) or not intents:
        add("intent_valid", "need_clarification", "intents 为空，无法判断本轮目标",
            "从合法集合中选一个或多个意图")
    else:
        bad = [i for i in intents if i not in VALID_INTENTS]
        if bad:
            add("intent_valid", "reject", f"非法意图 {bad}", f"合法集合：{sorted(VALID_INTENTS)}")
        else:
            add("intent_valid", "pass", f"意图合法：{intents}")

    # 4. 能力 code 必须锚定到真实条目（防幻觉核心）
    codes = collect_cap_codes(registry, ledger)
    claimed = intent.get("capabilities") or []
    hallucinated = [c for c in claimed if c not in codes]
    if hallucinated:
        add("cap_anchored", "reject",
            f"能力 code 无法在 registry/账本中锚定：{hallucinated}",
            "改用真实存在的 code，或先通过 ledger-steward 建立能力")
    else:
        add("cap_anchored", "pass", f"{len(claimed)} 个能力 code 均已锚定")

    # 5. 写入范围必须是合法权限子集
    scopes = intent.get("write_scope") or ["none"]
    bad_scope = [s for s in scopes if s not in VALID_SCOPES]
    if bad_scope:
        add("scope_valid", "reject", f"非法写入范围 {bad_scope}",
            f"合法集合：{sorted(VALID_SCOPES)}")
    else:
        add("scope_valid", "pass", f"写入范围合法：{scopes}")

    # 5b. 只读意图不得声明任何写入（修复压测暴露的越权漏洞）
    READ_ONLY_INTENTS = {"verify", "route", "meta"}
    effective_write = [s for s in scopes if s != "none"]
    if any(i in READ_ONLY_INTENTS for i in intents) and effective_write:
        add("readonly_no_write", "reject",
            f"只读意图 {[i for i in intents if i in READ_ONLY_INTENTS]} 却声明写入 {effective_write}",
            "只读意图的 write_scope 必须为 ['none']")
    else:
        add("readonly_no_write", "pass", "只读意图未声明写入")

    # 5c. 多业务意图竞争必须让人确认（对齐 route_expert 的 clarification 逻辑）
    business = [i for i in intents if i not in ("route", "meta")]
    if len(business) > 1:
        add("intent_unambiguous", "need_clarification",
            f"检测到多个竞争业务意图 {business}，不能静默选一个执行",
            "请人明确本轮唯一目标，或确认优先级")
    else:
        add("intent_unambiguous", "pass", "业务意图唯一")

    # 6. 元指令必须显式标注，且必须带开放问题（不能静默当业务任务）
    is_meta = "meta" in intents
    open_q = intent.get("open_questions") or []
    if is_meta and not open_q:
        add("meta_disclosed", "need_clarification",
            "检测到编排类元指令但未提供开放问题，不能静默路由",
            "补充 open_questions：要治理哪个目标项目？是否涉及写操作？")
    elif is_meta:
        add("meta_disclosed", "need_clarification",
            f"元指令需人确认（{len(open_q)} 个开放问题）",
            "请人逐条回答后重新提交")
    else:
        add("meta_disclosed", "pass", "非元指令，无额外披露要求")

    # 汇总结论：任一 reject -> reject；否则任一 need_clarification -> need_clarification；否则 allow
    statuses = [c["status"] for c in checks]
    if "reject" in statuses:
        verdict = "reject"
    elif "need_clarification" in statuses:
        verdict = "need_clarification"
    else:
        verdict = "allow"

    return {
        "schema": SCHEMA,
        "verdict": verdict,
        "checks": checks,
        "evidence": {
            "registry_codes": len(codes),
            "claimed_codes": len(claimed),
        },
        "recomputed": True,
    }


def gate(target: Path, intent_file: Path) -> dict:
    """供 route_expert 等编排层调用的便捷入口：读三份 JSON -> validate 结论。

    纯只读；缺文件时返回 reject 结论而非抛异常，保持 fail-closed。
    """
    rp = Path(target) / "governance" / "registry.json"
    lp = Path(target) / "governance" / "DECISION_LEDGER.json"
    ip = Path(intent_file)
    missing = [str(p) for p in (rp, lp, ip) if not p.exists()]
    if missing:
        return {"schema": SCHEMA, "verdict": "reject", "checks": [
            {"id": "inputs_exist", "status": "reject",
             "reason": "缺少输入文件：" + ", ".join(missing), "fix": "补齐后重试"}],
            "evidence": {}, "recomputed": True}
    return validate(load_json(ip), load_json(rp), load_json(lp))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="复述门（只读结构化意图校验）")
    ap.add_argument("--target", required=True, help="项目根（含 governance/）")
    ap.add_argument("--intent-file", required=True, help="intent.json 路径")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    args = ap.parse_args(argv)

    target = Path(args.target)
    registry_path = target / "governance" / "registry.json"
    ledger_path = target / "governance" / "DECISION_LEDGER.json"
    for p in (registry_path, ledger_path, Path(args.intent_file)):
        if not p.exists():
            print(f"missing: {p}", file=sys.stderr)
            return 3

    intent = load_json(Path(args.intent_file))
    registry = load_json(registry_path)
    ledger = load_json(ledger_path)
    result = validate(intent, registry, ledger)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"verdict: {result['verdict']}")
        for c in result["checks"]:
            mark = {"pass": "OK", "need_clarification": "ASK", "reject": "REJ"}[c["status"]]
            print(f"  [{mark}] {c['id']}: {c['reason']}")
            if c.get("fix"):
                print(f"         fix: {c['fix']}")

    return {"allow": 0, "need_clarification": 1, "reject": 2}[result["verdict"]]


if __name__ == "__main__":
    raise SystemExit(main())
