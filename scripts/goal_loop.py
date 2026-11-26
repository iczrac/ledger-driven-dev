#!/usr/bin/env python3
"""目标编排循环（goal-orchestrator 的执行器）：受控自动迭代，默认零写入。

第一性原理
----------
路线已定（route_expert）、链已展开（expert_run）、写入已被网关管住
（agent_gateway），但「围绕一个目标反复推进直到达标/超预算」仍缺一个
监督者。它必须满足三条铁律：
  1. 方向锁定：每轮重算方向锁，专家私自改目标立刻停；
  2. 预算有限：max_loops 用完未达成即 deactivated，不无限循环；
  3. 每轮都过验证：route → 队列 → 计划 → verify → 方向 → 推进，
     任一 fail-closed 点立即停止并给结构化原因。

本脚本**默认 dry-run**：只读账本，在内存里模拟循环并生成一份结构化
轨迹 + 待批准命令；不调用任何写工具、不改账本、不跑专家命令。
人拿到 dry-run 报告后，可用 --emit-apply 导出逐轮的网关命令，
由人按批准包逐条执行（create/approve 必须人批准，推进由预算授权）。

经验交接
--------
任务卡（``next_queue[].lessons``）里的前人教训必须真的到达执行者，
否则经验层只是另一座档案。本脚本做两件事：
  1. 白名单提取（``id/title/insight/action``）+ 条数上限，账本内部事实
     （scope/source_events/evidence）一律不外传，截断必须可见；
  2. 把经验交给 expert-run 的**独立 context 通道**——绝不拼进 intent，
     否则会抬高 route_expert 的 lesson 意图分，把实现任务误派给
     ledger-steward。intent 保持原样，路由行为零变化。

可复算：loop = f(ledger, goal_id, route_expert, verify_ledger, goal_ledger)；
同输入同版本必得一致轨迹。失败即 stop（不继续下一轮）。

用法
----
    python3 scripts/goal_loop.py --target P --goal-id G-001 --json
    python3 scripts/goal_loop.py --target P --goal-id G-001 --emit-apply
    python3 scripts/goal_loop.py --target P --goal-id G-001 --max-loops 3 --intent "..."
退出码：0=已达成/正常终止；1=超预算失活/方向偏移/验证失败；2=用法错误。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import goal_ledger  # noqa: E402
import route_expert as route  # noqa: E402

SCHEMA = "goal-loop/1"

# 经验外传白名单：只有这四个字段允许离开账本。
# scope / source_events / from_candidate / evidence 是账本内部事实
# （谁在什么时候踩了什么坑、依据哪条证据），带进执行者上下文等于外泄账本结构。
# 与 expert_run.py 的同名常量一一对应：两个信任边界各守一次。
LESSON_REF_FIELDS = ("id", "title", "insight", "action")
# 经验条数上限：经验条目无上限时 prompt 会膨胀。按「命中本任务 code／能力域
# 优先」排序取前 N，被截断的条目必须可见（写进 dropped / note），不静默丢。
LESSON_MAX_REFS = 10


def _verify_ledger_module(gov: Path):
    """优先用目标项目的治理副本，找不到时回落方法仓模板（只读 import）。"""
    import importlib.util
    for candidate in (gov / "verify_ledger.py", HERE.parent / "templates" / "verify_ledger.py"):
        if not candidate.is_file():
            continue
        spec = importlib.util.spec_from_file_location("_goal_verify", candidate)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
            return mod
        except (OSError, ValueError, ImportError):
            continue
    return None


def _halt(result: dict, reason: str, verdict: str) -> dict:
    result["verdict"] = verdict
    result["stop_reason"] = reason
    result["achieved"] = False
    return result


def _route_step(target: Path, display: str, intent: str) -> dict:
    """每轮重新路由：blocked / needs_clarification 一律 fail-closed。"""
    try:
        r = route.build(target, intent, "auto", display)
    except (OSError, ValueError) as exc:
        return {"ok": False, "reason": f"路由异常：{exc}", "expert": "", "chain": []}
    rr = r.get("route", {})
    if rr.get("blocked") or r.get("needs_clarification"):
        reason = (str((r.get("needs_clarification") or {}).get("question"))
                  if isinstance(r.get("needs_clarification"), dict)
                  else str(rr.get("reason", "路由未就绪")))
        return {"ok": False, "reason": reason, "expert": rr.get("expert", ""), "chain": []}
    chain = list((rr.get("handoff") or {}).get("chain") or [rr.get("expert")])
    return {"ok": True, "expert": rr.get("expert", ""), "chain": chain,
            "confidence": rr.get("confidence", ""), "intents": r.get("intents", [])}


def _verify_step(gov: Path, repo_root: Path, ledger: dict) -> dict:
    """跑真实 verify_ledger（只读）；返回 {ok, failed, na, checks}。"""
    mod = _verify_ledger_module(gov)
    if mod is None:
        return {"ok": False, "failed": 0, "na": 0, "checks": [],
                "reason": "找不到 verify_ledger.py，拒绝在无验证下推进"}
    reg_path = gov / "registry.json"
    # dry-run 在内存副本上推进，按设计不写盘；若把看板 EMBED 作为阻塞项，
    # 第 2 轮起必然因「账本已推进、看板未写」而假失败。此处只验账本自身
    # 不变量；真实写回由人逐条 apply 网关命令完成，届时 board 会同步。
    registry = json.loads(reg_path.read_text()) if reg_path.is_file() else None
    results = mod.verify(repo_root, ledger, registry, None, gov)
    failed = [r for r in results if r.get("status") == "fail"]
    na = [r for r in results if r.get("status") == "na"]
    return {"ok": not failed, "failed": len(failed), "na": len(na),
            "failed_ids": [r.get("id") for r in failed][:5],
            "checks": results}


def gateway_command(action: str, goal_id: str, *, agent: str,
                    approved_by: str = "", reason: str = "", extra: str = "") -> str:
    """生成一条人可复制执行的网关命令（本脚本不执行它）。"""
    parts = ["python3 scripts/agent_gateway.py request",
             f"--agent {agent}", f"--action {action}", f"--goal-id {goal_id}"]
    if approved_by:
        parts.append(f"--approved-by {approved_by}")
    if reason:
        parts.append(f"--reason \"{reason}\"")
    if extra:
        parts.append(extra)
    parts.append("--apply")
    return " ".join(parts)


def progress_fingerprint(ledger: dict, goal: dict, task: dict) -> str:
    """进展指纹 = 任务 + 判据相关能力等级 + 方法版本。

    dry-run 不写盘，真实工作完成前这三者不会变；连续相同即判定循环空转，
    不能靠烧完 max_loops 才失活。用 json 稳定序列化保证可复算。
    """
    import hashlib as _hl

    cm = ledger.get("capability_model") or {}
    caps = [c for p in cm.get("projects", []) for m in p.get("modules", [])
            for c in m.get("caps", []) if isinstance(c, dict)]
    by_code = {c.get("code"): c for c in caps}
    codes = sorted({str(c.get("target", "")) for c in goal.get("success_criteria", [])
                    if isinstance(c, dict)
                    and c.get("metric") in ("cap_level", "level_progress")})
    state = {
        "task": str(task.get("code", "")),
        "levels": {code: (by_code.get(code) or {}).get("level") for code in codes},
        "method_version": (ledger.get("governance_meta") or {}).get("method_version"),
    }
    blob = json.dumps(state, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
    return _hl.sha256(blob.encode("utf-8")).hexdigest()


def _lesson_priority(item: dict, task: dict) -> int:
    """经验与本任务的贴合度：命中能力 code 最高，其次能力域／项目／等级。

    任务卡若没带 scope（生成器只写白名单四字段），一律按 0 处理并保持原序——
    生成器已经按 scope 过滤过一遍，消费端不重复发明匹配规则，只在需要截断时
    用贴合度决定先留哪条。
    """
    scope = item.get("scope")
    if not isinstance(scope, dict):
        return 0
    code = str(task.get("code", "") or "")
    project = str(task.get("project", "") or "")
    domain = str(task.get("domain", "") or "")
    level = str(task.get("level", "") or "")
    caps = [str(x) for x in (scope.get("capabilities") or [])]
    projs = [str(x) for x in (scope.get("projects") or [])]
    doms = [str(x) for x in (scope.get("domains") or [])]
    lvls = [str(x) for x in (scope.get("levels") or [])]
    if code and code in caps:
        return 4
    if domain and domain in doms:
        return 3
    if project and project in projs:
        return 2
    if level and level in lvls:
        return 2
    if not (caps or projs or doms or lvls):
        return 1  # 全局经验：适用于所有任务
    return 0


def _lesson_refs(task: dict) -> dict:
    """从任务卡提取可外传的经验引用（白名单四字段 + 条数上限）。

    返回 {"lessons": [...], "total": n, "truncated": bool, "dropped": [id...]}：
    - 白名单：scope/source_events/from_candidate/evidence 一律不带出；
    - 上限：超过 LESSON_MAX_REFS 时按贴合度排序取前 N，稳定的 sort 保证
      同贴合度时保持任务卡原序；
    - 截断可见：被丢掉的 id 写进 dropped，不静默丢。
    """
    raw = task.get("lessons") if isinstance(task, dict) else None
    raw = raw if isinstance(raw, list) else []
    scored: list[tuple[int, dict]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        ref = {k: str(item.get(k, "") or "") for k in LESSON_REF_FIELDS}
        if not ref["id"]:
            continue
        scored.append((_lesson_priority(item, task), ref))
    scored.sort(key=lambda pair: -pair[0])  # 稳定排序：同分保持原序
    kept = [ref for _, ref in scored[:LESSON_MAX_REFS]]
    dropped = [ref["id"] for _, ref in scored[LESSON_MAX_REFS:]]
    return {"lessons": kept, "total": len(scored),
            "truncated": bool(dropped), "dropped": dropped}


def run(target: Path, goal_id: str, *, intent: str = "",
        max_loops: int | None = None, emit_apply: bool = False,
        stall_limit: int = 2) -> dict:
    """只读预演：在账本内存副本上模拟循环，不改盘、不跑专家命令。"""
    display = str(target)
    if not isinstance(stall_limit, int) or isinstance(stall_limit, bool) \
            or not 1 <= stall_limit <= 20:
        return _halt({"schema": SCHEMA, "target": display, "goal_id": goal_id,
                      "rounds": [], "commands": [], "mode": "dry-run"},
                     f"stall_limit 必须 1..20（当前 {stall_limit}）", "invalid")
    gov = target / "governance"
    ledger_path = gov / "DECISION_LEDGER.json"
    if not ledger_path.is_file():
        return _halt({"schema": SCHEMA, "target": display, "goal_id": goal_id,
                      "rounds": [], "commands": [], "mode": "dry-run"},
                     f"账本不存在：{ledger_path}", "invalid")
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _halt({"schema": SCHEMA, "target": display, "goal_id": goal_id,
                      "rounds": [], "commands": [], "mode": "dry-run"},
                     f"账本损坏：{exc}", "invalid")
    goal = goal_ledger.find_goal(ledger, goal_id)
    if goal is None:
        return _halt({"schema": SCHEMA, "target": display, "goal_id": goal_id,
                      "rounds": [], "commands": [], "mode": "dry-run"},
                     f"目标不存在：{goal_id}", "invalid")

    result = {
        "schema": SCHEMA, "target": display, "goal_id": goal_id,
        "mode": "dry-run" if not emit_apply else "apply-plan",
        "goal": {"description": goal.get("description", ""),
                 "status": goal.get("status", ""),
                 "max_loops": goal.get("max_loops", 0),
                 "current_loop": goal.get("current_loop", 0),
                 "direction_lock": goal.get("direction_lock", "")},
        "rounds": [], "commands": [], "verdict": "running",
        "stop_reason": "", "achieved": False,
    }
    # 只读账本副本：循环中所有推进都发生在副本上，绝不写回文件。
    sim = json.loads(json.dumps(ledger, ensure_ascii=False))

    if goal.get("status") in goal_ledger.TERMINAL_STATUS:
        return _halt(result, f"目标已是终态 {goal['status']}，不可再循环", "halted")
    if not goal_ledger.check_direction(goal):
        return _halt(result, "方向锁不匹配：目标疑似被私自修改，已停止", "direction_drift")

    budget = int(max_loops or goal.get("max_loops", 0))
    if budget < 1 or budget > int(goal.get("max_loops", 0)):
        return _halt(result, f"max_loops 必须 1..{goal.get('max_loops')}", "invalid")

    base_intent = intent or goal.get("description", "")
    cm = (sim.get("capability_model") or {})
    queue = list(cm.get("next_queue") or [])
    if not queue:
        return _halt(result, "next_queue 为空：无可推进任务，等待补队列", "no_queue")

    first_task = next((t for t in queue if str(t.get("code", "")) in base_intent), queue[0])
    last_fp = progress_fingerprint(sim, goal, first_task)
    stalled = 0

    for step in range(budget):
        cur = goal_ledger.find_goal(sim, goal_id)
        if cur["current_loop"] >= cur["max_loops"]:
            break
        round_no = cur["current_loop"] + 1
        rec: dict = {"round": round_no, "checks": []}

        # 1) 取与目标相关的一条 next_queue（按 code 命中优先）
        task = next((t for t in queue if str(t.get("code", "")) in base_intent), queue[0])
        # 经验交接：任务卡自带的前人教训必须跟着这一轮走到执行者手里。
        # 白名单 + 条数上限在这里做（账本 → 任务卡的信任边界）。
        lesson_view = _lesson_refs(task)
        rec["task"] = {"code": task.get("code", ""), "action": task.get("action", ""),
                       "lessons": lesson_view["lessons"]}
        if lesson_view["truncated"]:
            rec["task"]["lessons_truncated"] = True
            rec["task"]["lessons_dropped"] = lesson_view["dropped"]

        # 2) 每轮重新路由：用目标意图 + 任务动作，确保可识别且随任务变化
        round_intent = intent or (
            f"目标循环推进：{base_intent}；本轮任务：{task.get('action', '')}")
        r = _route_step(target, display, round_intent)
        rec["route"] = r
        if not r["ok"]:
            rec["checks"].append("route-fail-closed")
            result["rounds"].append(rec)
            return _halt(result, f"第 {round_no} 轮路由停止：{r['reason']}", "blocked")

        # 3) expert-run 只读计划（不执行命令）
        #    经验走**独立 context 通道**：intent 保持原样（经验文本绝不拼进
        #    intent——那会抬高 route_expert 的 lesson 意图分，把实现任务误派
        #    给 ledger-steward），路由行为零变化。
        try:
            plan = __import__("expert_run").run(
                target, f"{task.get('action', '')}：{base_intent}",
                context={"task_code": str(task.get("code", "") or ""),
                         "lessons": lesson_view["lessons"],
                         "total": lesson_view["total"],
                         "truncated": lesson_view["truncated"],
                         "dropped": lesson_view["dropped"]})
            rec["plan"] = {"verdict": plan.get("verdict"),
                           "approval_count": plan.get("approval_bundle", {}).get("count", 0),
                           "chain_len": len(plan.get("chain") or []),
                           "task_context": plan.get("task_context", {})}
        except (OSError, ValueError) as exc:
            rec["plan"] = {"verdict": "error", "reason": str(exc)}

        # 4) 验证（真实 verify_ledger，fail 即停）
        v = _verify_step(gov, target.resolve(), sim)
        rec["verify"] = {"ok": v["ok"], "failed": v["failed"], "na": v["na"],
                         "failed_ids": v.get("failed_ids", [])}
        if not v["ok"]:
            rec["checks"].append("verify-fail")
            result["rounds"].append(rec)
            return _halt(result, f"第 {round_no} 轮验证失败：{v.get('failed_ids')}", "verify_failed")

        # 5) 方向检查
        if not goal_ledger.check_direction(cur):
            rec["checks"].append("direction-drift")
            result["rounds"].append(rec)
            return _halt(result, f"第 {round_no} 轮方向漂移：需人批准调整", "direction_drift")

        # 6) 推进（内存副本）
        goal_ledger.advance_goal(sim, goal_id, actor="goal-orchestrator(dry-run)")
        result["commands"].append(
            gateway_command("goal-advance", goal_id,
                            agent="goal-orchestrator", reason=f"第 {round_no} 轮通过验证"))
        rec["advanced_to"] = goal_ledger.find_goal(sim, goal_id)["current_loop"]
        result["rounds"].append(rec)

        # 7) 达成判定（指向 sim 的目标，注入验证明细）
        cur2 = goal_ledger.find_goal(sim, goal_id)
        cur2["_verify_detail"] = {"checks": v["checks"]}
        ev = goal_ledger.evaluate_criteria(sim, cur2)
        cur2.pop("_verify_detail", None)
        rec["criteria"] = ev
        if ev["all_met"]:
            goal_ledger.achieve_goal(sim, goal_id, actor="goal-orchestrator(dry-run)")
            result["commands"].append(
                gateway_command("goal-achieve", goal_id, agent="goal-orchestrator",
                                reason="success_criteria 全部满足"))
            result["achieved"] = True
            result["goal"]["final_status"] = "achieved"
            result["goal"]["final_loop"] = cur2["current_loop"]
            return _halt(result, "目标达成", "achieved")

        # 8) 停滞检测：任务/相关能力等级/版本连续不变 → 空转，暂停而非烧预算
        fp = progress_fingerprint(sim, goal, task)
        rec["progress"] = {"fingerprint": fp, "stalled_rounds": stalled + 1}
        if fp == last_fp:
            stalled += 1
        else:
            stalled = 0
        last_fp = fp
        rec["progress"]["stalled_rounds"] = stalled
        if stalled >= stall_limit:
            goal_ledger.pause_goal(sim, goal_id, actor="goal-orchestrator(dry-run)",
                                   reason="连续无进展")
            result["commands"].append(
                gateway_command("goal-pause", goal_id, agent="goal-orchestrator",
                                reason=f"连续 {stalled} 轮任务/能力等级/版本无变化"))
            result["proposal"] = {
                "original_goal": goal.get("description", ""),
                "proposed_change": "先完成 next_queue 中的队列任务并重算能力模型/绑定实测证据，"
                                   "再 resume 本目标",
                "rationale": f"连续 {stalled} 轮进展指纹相同，循环空转；"
                             "预算推进不等于真实工作推进",
                "impact": "目标暂停（可 resume）；不消耗剩余预算、不改方向锁、不写事实源",
            }
            result["goal"]["final_status"] = "paused"
            result["goal"]["final_loop"] = cur2["current_loop"]
            return _halt(result,
                         f"连续 {stalled} 轮无进展，已暂停待真实工作推进（stagnated）",
                         "stagnated")

    # 预算用尽仍未达成 → 失活
    final = goal_ledger.find_goal(sim, goal_id)
    result["commands"].append(
        gateway_command("goal-deactivate", goal_id, agent="goal-orchestrator",
                        reason="max_loops 用尽仍未达成"))
    result["goal"]["final_status"] = "deactivated"
    result["goal"]["final_loop"] = final["current_loop"]
    return _halt(result, "循环预算用尽，目标失活（deactivated）", "deactivated")


def render(out: dict) -> str:
    lines = [f"目标循环 → {out.get('verdict', '?')}｜{out.get('stop_reason', '')}"]
    g = out.get("goal", {})
    lines.append(f"目标 {out.get('goal_id')}：{g.get('description', '')[:60]}")
    lines.append(f"预算 {g.get('current_loop')}/{g.get('max_loops')}｜"
                 f"终态 {g.get('final_status', g.get('status', '-'))}")
    for r in out.get("rounds", []):
        v = r.get("verify", {})
        lines.append(f"  第 {r['round']} 轮：路由={r.get('route', {}).get('expert', '-')}"
                     f"｜验证 fail={v.get('failed', '?')}｜"
                     f"判据 {r.get('criteria', {}).get('met_count', '-')}"
                     f"/{r.get('criteria', {}).get('total', '-')}"
                     f"｜推进至 {r.get('advanced_to', '-')}")
        t = r.get("task", {})
        ls = t.get("lessons") or []
        if ls:
            ids = ",".join(str(x.get("id", "")) for x in ls)
            lines.append(f"    经验 {len(ls)} 条：{ids}"
                         + ("（已截断）" if t.get("lessons_truncated") else ""))
            for l in ls[:3]:
                lines.append(f"      - [{l.get('id', '')}] {l.get('action', '')[:70]}")
            if len(ls) > 3:
                lines.append(f"      ... 另有 {len(ls) - 3} 条，见 JSON")
    if out.get("commands"):
        lines.append(f"待批准命令 {len(out['commands'])} 条（本脚本未执行）：")
        for c in out["commands"][:12]:
            lines.append("  - " + c)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default=".", help="被治理项目根目录")
    ap.add_argument("--goal-id", required=True, help="目标 ID")
    ap.add_argument("--intent", default="", help="覆盖本轮意图（默认用目标描述）")
    ap.add_argument("--max-loops", type=int, default=0, help="本次模拟预算上限（不超过目标预算）")
    ap.add_argument("--stall-limit", type=int, default=2,
                    help="连续无进展轮数阈值 1-20（默认 2，达到即 stagnated 暂停）")
    ap.add_argument("--emit-apply", action="store_true", help="输出待批准网关命令清单")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)
    out = run(Path(args.target).expanduser().resolve(), args.goal_id,
              intent=args.intent, max_loops=args.max_loops,
              emit_apply=args.emit_apply, stall_limit=args.stall_limit)
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render(out))
    return 0 if out["verdict"] in ("achieved", "halted", "stagnated") else 1


if __name__ == "__main__":
    raise SystemExit(main())
