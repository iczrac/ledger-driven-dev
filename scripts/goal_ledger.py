#!/usr/bin/env python3
"""目标编排的纯函数层：目标对象、方向锁、预算推进、调整提议。

第一性原理
----------
expert-run 能把路由展开成批准包，但它回答的是「这一步谁做」；
当目标需要跨多轮、且每轮都要重新路由时，缺的是三样东西：
  1. 一个不可被专家篡改的目标物件（方向锁）；
  2. 一个有限的循环预算（max_loops / current_loop）；
  3. 一条「要改目标就停、由人批准」的升级路径。

本模块只做纯函数：给定账本与输入，返回新账本或结构化结果，
不写文件、不跑命令、不 import agent_gateway（避免循环依赖）。
所有落盘都由 agent_gateway.dispatch 统一执行，保证单写者与审计。

核心纪律
--------
- 方向锁 lock = sha256(canonical(description, success_criteria))。
  一旦 active，任何专家写入只要改了这两项，verify_ledger 的
  goal_loop_valid 就会 fail。专有权在人：goal-approve 动作
  需 --approved-by，且唯一能重算 lock 的入口是 approve_goal。
- 预算只在循环内推进：advance_goal 仅允许 active 且 current_loop<max_loops；
  超预算由 deactivate_goal 置 deactivated，不再活跃。
- achieved / deactivated 是终态，不得再 advance。
- 调整提议只写 goal['proposals']，绝不改 description / success_criteria。

可复算：所有摘要用 json.dumps(sort_keys=True, separators=(',', ':'))。
退出码不适用（纯库）；错误一律抛 ValueError，由调用方 fail-closed。
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

GOALS_SCHEMA = "goals/1"
VALID_STATUS = ("active", "paused", "achieved", "deactivated")
TERMINAL_STATUS = ("achieved", "deactivated")
GOAL_ID_RE = re.compile(r"^G-[A-Z0-9][A-Z0-9-]{1,47}$")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical_lock(description: str, criteria: list | dict) -> str:
    """方向锁：描述 + 机读成功判据的规范化摘要。改目标必须先解这条锁。"""
    payload = {"description": description, "success_criteria": criteria}
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def goals_of(ledger: dict) -> dict:
    g = ledger.get("goals")
    return g if isinstance(g, dict) else {"schema": GOALS_SCHEMA, "items": []}


def items_of(ledger: dict) -> list[dict]:
    return [x for x in goals_of(ledger).get("items", []) if isinstance(x, dict)]


def find_goal(ledger: dict, goal_id: str) -> dict | None:
    return next((g for g in items_of(ledger) if g.get("goal_id") == goal_id), None)


# 判据指标全表：新增指标必须同时进这里、validate_criteria 与 evaluate_criteria。
SUPPORTED_METRICS = ("cap_level", "queue_empty", "invariant_all",
                     "method_version", "level_progress")
VERSION_OPS = ("gte", "gt", "eq", "ne", "lte", "lt", ">=", ">", "==", "!=", "<=", "<")


def version_tuple(value) -> tuple[int, ...]:
    """语义版本转可比较元组；与 upgrade._version_tuple 语义一致（标准库、纯函数）。

    非数字段按 0 处理，保证 2.9.0 < 2.10.0（v2.10 踩过字符串比较的坑）。
    """
    parts: list[int] = []
    for piece in str(value or "").strip().split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while parts and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def compare_version(current, target, op: str) -> bool:
    """按语义版本比较；未知 op 一律 False（fail-closed）。"""
    a, b = version_tuple(current), version_tuple(target)
    return {
        "gte": a >= b, ">=": a >= b, "gt": a > b, ">": a > b,
        "eq": a == b, "==": a == b, "ne": a != b, "!=": a != b,
        "lte": a <= b, "<=": a <= b, "lt": a < b, "<": a < b,
    }.get(op, False)


def validate_criteria(criteria) -> list[str]:
    """机读成功判据必须是非空列表，每项含 id/metric/target/op；指标参数需自洽。"""
    errors: list[str] = []
    if not isinstance(criteria, list) or not criteria:
        return ["success_criteria 必须是非空数组"]
    seen: set[str] = set()
    for i, c in enumerate(criteria):
        if not isinstance(c, dict):
            errors.append(f"判据[{i}]非对象")
            continue
        cid = str(c.get("id", ""))
        if not cid or cid in seen:
            errors.append(f"判据[{i}] id 缺失或重复：{cid}")
        seen.add(cid)
        metric, op = str(c.get("metric", "")), str(c.get("op", ""))
        if not metric or "target" not in c or not op:
            errors.append(f"判据[{i}] 缺 metric/target/op")
            continue
        if metric not in SUPPORTED_METRICS:
            errors.append(f"判据[{i}] 未知 metric={metric}")
        elif metric == "method_version":
            if not version_tuple(c.get("target")):
                errors.append(f"判据[{i}] method_version.target 非法：{c.get('target')}")
            if op not in VERSION_OPS:
                errors.append(f"判据[{i}] method_version.op 非法：{op}")
        elif metric == "level_progress":
            if not str(c.get("target", "")):
                errors.append(f"判据[{i}] level_progress 缺能力 code")
            if "baseline" not in c or not isinstance(c.get("baseline"), int) \
                    or isinstance(c.get("baseline"), bool) or c["baseline"] < 0:
                errors.append(f"判据[{i}] level_progress.baseline 须为非负整数")
            try:
                if int(c.get("value", 1)) < 1:
                    errors.append(f"判据[{i}] level_progress.value 须 >= 1")
            except (TypeError, ValueError):
                errors.append(f"判据[{i}] level_progress.value 非法")
    return errors


def create_goal(ledger: dict, *, goal_id: str, description: str,
                success_criteria: list, max_loops: int,
                authorized_by: str, approved_by: str,
                now: str | None = None) -> dict:
    """人批准创建目标。authorized_by 是授权人；approved_by 是批准落盘的人。

    Agent 不得自批准：调用方（网关）负责校验 approved_by != agent。
    """
    if not GOAL_ID_RE.fullmatch(goal_id or ""):
        raise ValueError("goal_id 非法：应为 G- 开头、2-48 位大写字母数字连字符")
    if not authorized_by or not approved_by:
        raise ValueError("创建目标必须同时有 authorized_by 与 approved_by（人）")
    if find_goal(ledger, goal_id):
        raise ValueError(f"目标 {goal_id} 已存在")
    errs = validate_criteria(success_criteria)
    if errs:
        raise ValueError("；".join(errs))
    if not isinstance(max_loops, int) or isinstance(max_loops, bool) or not 1 <= max_loops <= 100:
        raise ValueError("max_loops 必须是 1-100 的整数")
    if not isinstance(description, str) or not description.strip():
        raise ValueError("description 不得为空")
    stamp = now or _now()
    goal = {
        "goal_id": goal_id, "description": description.strip(),
        "success_criteria": success_criteria,
        "max_loops": max_loops, "current_loop": 0, "status": "active",
        "authorized_by": authorized_by, "approved_by": approved_by,
        "created_at": stamp, "updated_at": stamp,
        "direction_lock": canonical_lock(description.strip(), success_criteria),
        "stop_reason": "", "proposals": [], "audit": [],
    }
    goals = goals_of(ledger)
    goals.setdefault("items", []).append(goal)
    ledger["goals"] = goals
    _audit(goal, "create", authorized_by, approved_by, stamp,
           f"创建目标，预算 {max_loops} 轮")
    return goal


def _audit(goal: dict, action: str, actor: str, approved_by: str,
           at: str, detail: str) -> dict:
    log = goal.setdefault("audit", [])
    entry = {"seq": len(log) + 1, "at": at, "action": action, "actor": actor,
             "approved_by": approved_by, "detail": detail}
    log.append(entry)
    goal["updated_at"] = at
    return entry


def check_direction(goal: dict) -> bool:
    """方向是否仍锁定：当前描述/判据的摘要与创建时锁一致。"""
    expected = canonical_lock(goal.get("description", ""),
                              goal.get("success_criteria", []))
    return expected == goal.get("direction_lock")


def advance_goal(ledger: dict, goal_id: str, *, actor: str,
                 at: str | None = None) -> dict:
    """循环内推进一轮。仅 active 且未超预算可推进；超预算显式拒绝。"""
    goal = find_goal(ledger, goal_id)
    if goal is None:
        raise ValueError(f"目标不存在：{goal_id}")
    if not check_direction(goal):
        raise ValueError("方向锁不匹配：疑似专家篡改目标，已拒绝推进")
    if goal["status"] != "active":
        raise ValueError(f"目标状态 {goal['status']} 不可推进（须 active）")
    if goal["current_loop"] >= goal["max_loops"]:
        raise ValueError("预算已用尽：先 deactivate，不得继续推进")
    stamp = at or _now()
    goal["current_loop"] += 1
    _audit(goal, "advance", actor, "", stamp,
           f"第 {goal['current_loop']}/{goal['max_loops']} 轮完成")
    return goal


def deactivate_goal(ledger: dict, goal_id: str, *, actor: str, reason: str,
                    at: str | None = None) -> dict:
    """超预算 / 方向偏移 / 验证失败时失活。失活是终态。"""
    goal = find_goal(ledger, goal_id)
    if goal is None:
        raise ValueError(f"目标不存在：{goal_id}")
    if goal["status"] in TERMINAL_STATUS:
        raise ValueError(f"目标已是终态 {goal['status']}")
    stamp = at or _now()
    goal["status"] = "deactivated"
    goal["stop_reason"] = reason or "未达目标"
    _audit(goal, "deactivate", actor, "", stamp, goal["stop_reason"])
    return goal


def achieve_goal(ledger: dict, goal_id: str, *, actor: str,
                 at: str | None = None) -> dict:
    """达标：终态，验收入口只由验证结果驱动。"""
    goal = find_goal(ledger, goal_id)
    if goal is None:
        raise ValueError(f"目标不存在：{goal_id}")
    if goal["status"] in TERMINAL_STATUS:
        raise ValueError(f"目标已是终态 {goal['status']}")
    if not check_direction(goal):
        raise ValueError("方向锁不匹配，拒绝标记达成")
    stamp = at or _now()
    goal["status"] = "achieved"
    goal["stop_reason"] = "success_criteria 全部满足"
    _audit(goal, "achieve", actor, "", stamp, goal["stop_reason"])
    return goal


def pause_goal(ledger: dict, goal_id: str, *, actor: str, reason: str,
               at: str | None = None) -> dict:
    goal = find_goal(ledger, goal_id)
    if goal is None or goal["status"] in TERMINAL_STATUS:
        raise ValueError("目标不存在或已是终态")
    stamp = at or _now()
    goal["status"] = "paused"
    goal["stop_reason"] = reason or "人工暂停"
    _audit(goal, "pause", actor, "", stamp, goal["stop_reason"])
    return goal


def resume_goal(ledger: dict, goal_id: str, *, actor: str,
                at: str | None = None) -> dict:
    goal = find_goal(ledger, goal_id)
    if goal is None or goal["status"] != "paused":
        raise ValueError("只有 paused 目标可恢复")
    if not check_direction(goal):
        raise ValueError("方向锁不匹配，拒绝恢复")
    stamp = at or _now()
    goal["status"] = "active"
    goal["stop_reason"] = ""
    _audit(goal, "resume", actor, "", stamp, "恢复循环")
    return goal


def propose_change(ledger: dict, goal_id: str, *, actor: str,
                   original_goal: str, proposed_change: str,
                   rationale: str, impact: str,
                   proposed_criteria: list | None = None,
                   proposed_description: str | None = None,
                   at: str | None = None) -> dict:
    """专家/人提出调整提议：只追加到 proposals，不触碰目标本身。"""
    goal = find_goal(ledger, goal_id)
    if goal is None:
        raise ValueError(f"目标不存在：{goal_id}")
    if not all([original_goal, proposed_change, rationale, impact]):
        raise ValueError("提议须含原目标/建议变更/理由/影响")
    if proposed_criteria is not None:
        errs = validate_criteria(proposed_criteria)
        if errs:
            raise ValueError("；".join(errs))
    stamp = at or _now()
    proposals = goal.setdefault("proposals", [])
    proposal = {
        "id": f"P-{len(proposals) + 1:03d}", "at": stamp, "actor": actor,
        "original_goal": original_goal, "proposed_change": proposed_change,
        "rationale": rationale, "impact": impact,
        "proposed_description": proposed_description,
        "proposed_criteria": proposed_criteria,
        "new_lock": (canonical_lock(proposed_description, proposed_criteria)
                     if proposed_description is not None and proposed_criteria is not None
                     else None),
        "status": "pending", "approved_by": "", "resolved_at": "",
    }
    proposals.append(proposal)
    _audit(goal, "propose", actor, "", stamp, f"提出调整 {proposal['id']}")
    return proposal


def approve_change(ledger: dict, goal_id: str, proposal_id: str, *,
                   approved_by: str, at: str | None = None) -> dict:
    """人批准提议后才改目标并重算方向锁。专家无权调用本函数。"""
    goal = find_goal(ledger, goal_id)
    if goal is None:
        raise ValueError(f"目标不存在：{goal_id}")
    if not approved_by:
        raise ValueError("批准调整必须由人提供 approved_by")
    proposal = next((p for p in goal.get("proposals", [])
                     if p.get("id") == proposal_id), None)
    if proposal is None:
        raise ValueError(f"提议不存在：{proposal_id}")
    if proposal.get("status") != "pending":
        raise ValueError(f"提议已处理：{proposal['status']}")
    stamp = at or _now()
    if proposal.get("proposed_description") is not None:
        goal["description"] = proposal["proposed_description"]
    if proposal.get("proposed_criteria") is not None:
        goal["success_criteria"] = proposal["proposed_criteria"]
    goal["direction_lock"] = canonical_lock(goal["description"],
                                           goal["success_criteria"])
    proposal["status"] = "approved"
    proposal["approved_by"] = approved_by
    proposal["resolved_at"] = stamp
    _audit(goal, "approve-change", approved_by, approved_by, stamp,
           f"人批准 {proposal_id}，方向锁重算")
    return proposal


def reject_change(ledger: dict, goal_id: str, proposal_id: str, *,
                  approved_by: str, reason: str = "",
                  at: str | None = None) -> dict:
    goal = find_goal(ledger, goal_id)
    proposal = next((p for p in (goal or {}).get("proposals", [])
                     if p.get("id") == proposal_id), None)
    if goal is None or proposal is None:
        raise ValueError("目标或提议不存在")
    if proposal.get("status") != "pending":
        raise ValueError("提议已处理")
    stamp = at or _now()
    proposal["status"] = "rejected"
    proposal["approved_by"] = approved_by
    proposal["resolved_at"] = stamp
    proposal["reject_reason"] = reason
    _audit(goal, "reject-change", approved_by, approved_by, stamp,
           f"人驳回 {proposal_id}")
    return proposal


def evaluate_criteria(ledger: dict, goal: dict) -> dict:
    """只读评估机读判据；未知 metric / 非法 op 一律 false（fail-closed）。

    - cap_level:       capability_model 中 code 的 level 与 value 比较
    - queue_empty:     next_queue 为空
    - invariant_all:   verify 结果全部非 fail（由循环注入 verify_detail）
    - method_version:  governance_meta.method_version 与 target 语义版本比较
    - level_progress:  code 的 level 相对 baseline 的提升量 >= value
    判据与 verify_ledger 相互独立：verify 是门禁，evaluate 是达成判定。
    """
    cm = ledger.get("capability_model", {})
    caps = [c for p in cm.get("projects", []) for m in p.get("modules", [])
            for c in m.get("caps", []) if isinstance(c, dict)]
    by_code = {c.get("code"): c for c in caps}
    results = []
    for c in goal.get("success_criteria", []):
        if not isinstance(c, dict):
            results.append({"id": "", "met": False, "reason": "判据非对象"})
            continue
        metric, target, op = str(c.get("metric", "")), c.get("target"), str(c.get("op", ""))
        met, reason = False, "未知 metric"
        if metric == "cap_level":
            cap = by_code.get(str(target))
            lv = cap.get("level") if cap else None
            try:
                n = int(lv) if lv is not None else -1
                threshold = int(c.get("value", 3))
                met = n >= threshold if op in (">=", "gte") else n == threshold
                reason = f"{target} level={lv} op={op} value={threshold}"
            except (TypeError, ValueError):
                reason = f"{target} level 非法：{lv}"
        elif metric == "queue_empty":
            q = cm.get("next_queue", [])
            met = not q
            reason = f"next_queue={len(q)}"
        elif metric == "invariant_all":
            verify = goal.get("_verify_detail") or {}
            fails = [r.get("id") for r in verify.get("checks", [])
                     if isinstance(r, dict) and r.get("status") == "fail"]
            met = not fails and bool(verify)
            reason = f"verify fail={fails[:3]}" if fails else "verify 未提供或全通过"
        elif metric == "method_version":
            current = (ledger.get("governance_meta") or {}).get("method_version", "0")
            met = compare_version(current, c.get("target"), op)
            reason = f"method_version={current} op={op} target={c.get('target')}"
        elif metric == "level_progress":
            cap = by_code.get(str(target))
            lv = cap.get("level") if cap else None
            try:
                base, need = int(c.get("baseline", 0)), int(c.get("value", 1))
                delta = (int(lv) if lv is not None else 0) - base
                met = delta >= need if op in (">=", "gte") else delta == need
                reason = (f"{target} level={lv} baseline={base} "
                          f"delta={delta} op={op} value={need}")
            except (TypeError, ValueError):
                reason = f"{target} level 非法：{lv}"
        results.append({"id": str(c.get("id", "")), "met": bool(met), "reason": reason})
    all_met = bool(results) and all(r["met"] for r in results)
    return {"all_met": all_met, "criteria": results,
            "met_count": sum(1 for r in results if r["met"]),
            "total": len(results)}
