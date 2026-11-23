#!/usr/bin/env python3
"""多 Agent 接入网关：身份 → 授权 → 前置条件 → 写入 → 审计的唯一执行点。

第一性原理
----------
v0.9.0 的权限边界写在七份 `EXPERT.md` 的散文里，路由输出的是「建议」，
`scenario_guard.py` 是**只读**的。也就是说：Agent 只要有 shell，就能直接跑
`ledger_decide.py` / `lifecycle.py` 绕过全部纪律。声明的权限不是权限，
**在写入口强制执行的最小权限才是权限**。

本网关补的是这一层，判定顺序固定且默认拒绝：

    identity → role → scope → CAS → registry CAS → lease → preflight → approval
             → [write] → audit(append-only) → board sync

关键设计
--------
1. **单一事实源**：Agent 名册、租约、审计、版本号都在账本 `access` 字段，
   不新建 AGENTS.yaml / 权限表 / 审计日志；EMBED 随账本同步。
2. **升级是接入的前置条件**：`access` 不存在时所有请求一律拒绝，
   必须先跑 `upgrade.py apply --approved-by <人>` 建立默认拒绝登记。
3. **权限授予者 ≠ 被授权者**：`register` 只能由人批准；Agent 不得自注册、
   不得自我批准解冻/归档，也不得给自己加角色。
4. **CAS 双轨**：`current_fingerprint` 检测能力状态漂移；
   `registry.json` 的 sha256 检测手写清单漂移（v0.9.0 的 F7 缺口，只做检测不做合并）。
5. **并发三锁**：`fcntl.flock` 保证读-判-写原子；按编码租约避免两人改同一能力；
   `access.revision` 让每次写入都可数、可回放。
6. **审计不可绕过**：许可与拒绝都留痕；`--apply` 才会真的写，默认 dry-run。

诚实边界
--------
这是**策略执行点，不是操作系统沙箱**。若平台把 shell 与目标项目目录同时暴露给
Agent，它仍可直接调用底层脚本。要强隔离必须用容器 / 只读挂载 / CI 只接受网关产物。
本仓库的做法是：只把本网关注册为 Agent 的写工具，底层脚本保留为人工逃生舱，
并由 `check.sh` 的端到端阶段验证「网关写入后 31 条不变量仍成立」。

用法
----
    python3 scripts/agent_gateway.py --target P status --json
    python3 scripts/agent_gateway.py --target P register \
        --agent ci-agent --role loop-executor --approved-by 张三 --apply
    python3 scripts/agent_gateway.py --target P request --agent ci-agent \
        --action claim --code DEMO.API.QUERY.01 --expect-fingerprint <fp> --json
    # 加 --apply 才真正写入；许可类动作请把 permit.fingerprint 交给底层工具

输出 schema: agent-gate/1。退出码：0 允许/成功；1 拒绝；2 定义自检失败。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ledger_io import (current_fingerprint, load_ledger, registry_sha,  # noqa: E402
                       write_ledger)
from scenario_guard import (SUPPORTED_LEDGER_VERSIONS, collect as guard_collect,  # noqa: E402
                            evaluate as guard_evaluate)
import goal_ledger  # noqa: E402
import ledger_decide  # noqa: E402
import ledger_lesson  # noqa: E402
import lifecycle  # noqa: E402

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows 场景，见 E6 诚实边界
    fcntl = None

SCHEMA = "agent-gate/1"
ACCESS_SCHEMA = "access/1"
AGENT_RE = re.compile(r"^[a-z][a-z0-9-]{1,31}$")
LEASE_TTL_MINUTES = 120
LOCK_NAME = ".ledger-write.lock"

ROLE_POLICIES: dict[str, list[str]] = {
    "expert-router": ["status", "route"],
    "greenfield-architect": ["bootstrap", "status", "verify"],
    "project-archaeologist": ["discover", "status", "verify"],
    "ledger-steward": ["decide", "lesson-confirm", "lesson-dismiss", "retire",
                       "restore", "generate", "claim", "release", "status", "verify"],
    "evidence-auditor": ["status", "verify"],
    "loop-executor": ["code", "generate", "claim", "release", "status", "verify"],
    "release-steward": ["freeze", "unfreeze", "archive", "status", "verify"],
    "platform-steward": ["upgrade-plan", "status", "verify"],
    # 目标编排监督者：只在预算内推进/失活，创建与调整批准必须人批准。
    # 自己没有任何 ledger-write 的解释权，goal-create / goal-approve 的
    # approval=True 由 evaluate 的 human_approval 保证 approver != agent。
    "goal-orchestrator": ["goal-advance", "goal-achieve", "goal-deactivate",
                          "goal-pause", "goal-resume", "goal-propose",
                          "status", "verify"],
}

# kind: ledger-write = 网关亲自写；permit-only = 只签许可，由底层工具带 CAS 执行
ACTIONS: dict[str, dict] = {
    "decide": dict(kind="ledger-write", guard="decide", code=True, registry=True),
    "lesson-confirm": dict(kind="ledger-write", guard="lesson", code=False, registry=False),
    "lesson-dismiss": dict(kind="ledger-write", guard="lesson", code=False, registry=False),
    "claim": dict(kind="ledger-write", guard="claim", code=True, registry=False),
    "release": dict(kind="ledger-write", guard="release", code=True, registry=False),
    "freeze": dict(kind="ledger-write", guard="lifecycle", code=False, registry=False),
    "unfreeze": dict(kind="ledger-write", guard="lifecycle", code=False, registry=False,
                     approval=True),
    "archive": dict(kind="ledger-write", guard="lifecycle", code=False, registry=False,
                    approval=True),
    "retire": dict(kind="ledger-write", guard="lifecycle", code=True, registry=False),
    "restore": dict(kind="ledger-write", guard="lifecycle", code=True, registry=False),
    "generate": dict(kind="permit-only", guard="generate", code=False, registry=True),
    "code": dict(kind="permit-only", guard="code", code=True, registry=True),
    "bootstrap": dict(kind="permit-only", guard="bootstrap", code=False, registry=False),
    "discover": dict(kind="permit-only", guard="discover", code=False, registry=False),
    "upgrade-plan": dict(kind="permit-only", guard="status", code=False, registry=False),
    "status": dict(kind="permit-only", guard="status", code=False, registry=False),
    "verify": dict(kind="permit-only", guard="verify", code=False, registry=False),
    "route": dict(kind="permit-only", guard="status", code=False, registry=False),
    # 目标编排（v2.13.0）：除 create/approve/reject 外均为预算内自动推进。
    # guard 复用 status：冻结/归档期 READ 也受限，目标不得在冻结期写。
    "goal-create": dict(kind="ledger-write", guard="status", code=False, registry=False,
                        approval=True),
    "goal-approve": dict(kind="ledger-write", guard="status", code=False, registry=False,
                         approval=True),
    "goal-reject": dict(kind="ledger-write", guard="status", code=False, registry=False,
                        approval=True),
    "goal-advance": dict(kind="ledger-write", guard="status", code=False, registry=False),
    "goal-achieve": dict(kind="ledger-write", guard="status", code=False, registry=False),
    "goal-deactivate": dict(kind="ledger-write", guard="status", code=False, registry=False),
    "goal-pause": dict(kind="ledger-write", guard="status", code=False, registry=False),
    "goal-resume": dict(kind="ledger-write", guard="status", code=False, registry=False),
    "goal-propose": dict(kind="ledger-write", guard="status", code=False, registry=False),
}

LIFECYCLE_ACTIONS = {"freeze", "unfreeze", "archive", "retire", "restore",
                     "claim", "release"}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _access(ledger: dict) -> dict:
    a = ledger.get("access")
    return a if isinstance(a, dict) else {}


def register(ledger: dict, agent: str, role: str, approved_by: str,
             scopes: list[str] | None = None) -> dict:
    """人批准后才能登记 Agent；失败抛 ValueError，账本不变。"""
    if not AGENT_RE.fullmatch(agent or ""):
        raise ValueError("Agent 名非法（应为小写字母开头、2-32 位字母数字连字符）")
    if role not in ROLE_POLICIES:
        raise ValueError(f"未知角色：{role}（可选 {sorted(ROLE_POLICIES)}）")
    if not approved_by:
        raise ValueError("注册必须由人批准：--approved-by")
    if approved_by == agent:
        raise ValueError("Agent 不得自我批准注册（权限授予者 ≠ 被授权者）")
    acc = _access(ledger)
    if acc.get("schema") != ACCESS_SCHEMA:
        raise ValueError("账本没有 access 登记；先运行 upgrade.py apply --approved-by <人>")
    agents = acc.setdefault("agents", [])
    if any(a.get("id") == agent for a in agents):
        raise ValueError(f"Agent {agent} 已登记；要改角色请由人撤销后重新注册")
    item = {"id": agent, "role": role, "enabled": True, "scopes": scopes or [],
            "registered_at": _now(), "approved_by": approved_by}
    agents.append(item)
    _audit(acc, {"agent": "human:" + approved_by, "action": "register",
                 "code": agent, "outcome": "applied", "reason": "人工批准登记",
                 "fingerprint_before": current_fingerprint(ledger)},
           fingerprint_after=current_fingerprint(ledger))
    return item


def _audit(acc: dict, event: dict, fingerprint_after: str | None) -> dict:
    log = acc.setdefault("audit", [])
    entry = {"seq": len(log) + 1, "at": _now(), **event,
             "fingerprint_after": fingerprint_after}
    log.append(entry)
    acc["revision"] = int(acc.get("revision", 0)) + 1
    return entry


def _lease_owner(acc: dict, code: str, agent: str, now: datetime) -> str | None:
    for lease in acc.get("leases", []):
        if lease.get("code") != code or lease.get("agent") == agent:
            continue
        try:
            at = datetime.fromisoformat(str(lease.get("at", "")).replace("Z", "+00:00"))
            if at.tzinfo is None:
                at = at.replace(tzinfo=timezone.utc)
            if now - at < timedelta(minutes=LEASE_TTL_MINUTES):
                return str(lease.get("agent"))
        except ValueError:
            return str(lease.get("agent"))
    return None


def evaluate(ledger: dict, req: dict, guard_result: dict | None,
             registry_digest: str | None, now: datetime | None = None) -> dict:
    """纯函数：账本 + 请求 + 预检事实 → allow/deny。测试可直接构造输入。"""
    now = now or datetime.now(timezone.utc)
    checks: list[dict] = []

    def add(cid: str, ok: bool, reason: str, fix: str = "", warn: bool = False) -> None:
        checks.append({"id": cid, "status": "pass" if ok else ("warn" if warn else "deny"),
                       "reason": reason, "fix": fix})

    acc = _access(ledger)
    action = req.get("action", "")
    agent = req.get("agent", "")
    spec = ACTIONS.get(action)
    ok_schema = acc.get("schema") == ACCESS_SCHEMA
    add("access_registry", ok_schema,
        "接入登记已就绪" if ok_schema else "账本缺少 access 登记，默认拒绝",
        "" if ok_schema else "先运行 upgrade.py apply --approved-by <人>")
    if not spec:
        add("known_action", False, f"未知动作 {action}", "使用 status 查看 ACTIONS")
    agent_row = next((a for a in (acc.get("agents") or []) if a.get("id") == agent), None)
    known = agent_row is not None and bool(agent_row.get("enabled", False))
    add("agent_identity", known,
        f"已登记且启用：{agent}" if known else f"未登记 / 已禁用：{agent}",
        "" if known else "由人批准 register；不要换一个 id 绕过")

    if known and spec:
        role = str(agent_row.get("role", ""))
        allowed = action in ROLE_POLICIES.get(role, [])
        add("role_policy", allowed,
            f"{role} 允许 {action}" if allowed else f"{role} 无权执行 {action}",
            "" if allowed else "回到 expert-router 重新分派，不要借用其他 Agent 身份")
        scopes = list(agent_row.get("scopes") or [])
        if scopes and spec["code"]:
            code = str(req.get("code", ""))
            in_scope = any(code.startswith(s) for s in scopes)
            add("scope_policy", in_scope,
                "编码在授权范围内" if in_scope else f"{code} 超出 scopes {scopes}",
                "" if in_scope else "请人扩展 scopes 或改用有权限的 Agent")
        else:
            add("scope_policy", True, "未设 scopes 或该动作不需编码")

    fp = current_fingerprint(ledger)
    need_cas = bool(spec and (spec["kind"] == "ledger-write" or
                              action in ("generate", "code")))
    exp_fp = req.get("expect_fingerprint") or ""
    if need_cas:
        if not exp_fp:
            add("cas_fingerprint", False, "写入/许可类动作必须带读取时指纹",
                "传 --expect-fingerprint <current_fingerprint>")
        else:
            matched = exp_fp == fp
            add("cas_fingerprint", matched,
                "指纹一致" if matched else f"读取时 {exp_fp}，当前 {fp}：期间有人写过",
                "" if matched else "重新读取账本、合并变更后再请求")
    else:
        add("cas_fingerprint", True, "该动作不需要 CAS")

    if spec and spec["registry"]:
        exp_reg = req.get("expect_registry_sha") or ""
        if not exp_reg:
            add("registry_cas", False, "该动作依赖 registry.json，必须带 registry 摘要",
                "先跑 status 取 registry_sha256，再传 --expect-registry-sha")
        else:
            matched = exp_reg == registry_digest
            add("registry_cas", matched,
                "手写清单未变" if matched else "registry.json 在读取后被人改过（F7 检测）",
                "" if matched else "重新读取 registry.json 并用 git 人工合并冲突")
    else:
        add("registry_cas", True, "该动作不依赖手写清单")

    if spec and spec.get("approval"):
        approver = req.get("approved_by") or ""
        add("human_approval", bool(approver) and approver != agent,
            "人工批准已记录" if approver and approver != agent else
            "解冻/归档必须有人批准，且 Agent 不得自我批准",
            "" if approver and approver != agent else "传 --approved-by <人>")

    lc = ledger.get("lifecycle") if isinstance(ledger.get("lifecycle"), dict) else {}
    state = str(lc.get("state", "active"))
    writable = state == "active" or (state == "frozen" and action == "unfreeze")
    add("lifecycle_state", writable, f"生命周期 {state}",
        "" if writable else "归档是不可写终态；冻结需人批准解冻")

    ver = str(ledger.get("ledger_version", "1.0"))
    add("ledger_version", ver in SUPPORTED_LEDGER_VERSIONS, f"数据契约 {ver}",
        "" if ver in SUPPORTED_LEDGER_VERSIONS else "跨版本 fail-closed，先迁移")

    if spec and spec["code"] and req.get("code"):
        holder = _lease_owner(acc, str(req["code"]), agent, now)
        add("lease_free", holder is None,
            "无他人持有该编码租约" if holder is None else f"{req['code']} 由 {holder} 持有",
            "" if holder is None else "等待 release 或由人清理超时租约")
    else:
        add("lease_free", True, "无需租约")

    exp_rev = req.get("expect_revision")
    if exp_rev is not None and str(exp_rev) != str(acc.get("revision", 0)):
        add("revision", False, f"读取时 revision={exp_rev}，当前 {acc.get('revision', 0)}",
            "重新读取 access.revision 后重试")
    else:
        add("revision", True, "revision 一致（或未提供）", warn=exp_rev is None)

    if guard_result is not None and spec:
        mapped = spec["guard"]
        blocked = list(guard_result.get("blocked_actions") or [])
        add("preflight", mapped not in blocked,
            f"场景预检允许 {mapped}" if mapped not in blocked else
            f"场景预检阻止 {mapped}：{', '.join(blocked)}",
            "" if mapped not in blocked else "按 guard 的 fix 处理后重新请求")
    else:
        add("preflight", True, "未提供预检事实（仅单元测试构造）", warn=True)

    denied = [c["id"] for c in checks if c["status"] == "deny"]
    permit = None
    if not denied and spec:
        permit = {"fingerprint": fp, "registry_sha256": registry_digest,
                  "revision": acc.get("revision", 0), "kind": spec["kind"],
                  "lease_ttl_minutes": LEASE_TTL_MINUTES,
                  "note": ("许可类动作不代写；请把 fingerprint 交给底层工具的 "
                           "--expect-fingerprint") if spec["kind"] == "permit-only"
                          else "网关将亲自写入并同步看板"}
    return {"schema": SCHEMA, "agent": agent, "action": action,
            "code": req.get("code", ""), "decision": "deny" if denied else "allow",
            "denied_by": denied, "checks": checks, "permit": permit,
            "apply": bool(req.get("apply", False))}


def dispatch(ledger: dict, req: dict) -> tuple[dict, str]:
    """网关亲自写账本：只允许白名单动作，复用既有纯函数，不复制业务逻辑。"""
    a = req["action"]
    actor = req["agent"]
    if a in LIFECYCLE_ACTIONS:
        return lifecycle.apply(
            ledger, a, reason=req.get("reason", ""), actor=actor,
            approved_by=req.get("approved_by", ""), code=req.get("code", ""),
            superseded_by=req.get("superseded_by", ""))
    if a == "decide":
        e = ledger_decide.decide(ledger, req.get("code", ""),
                                 req.get("title", ""), req.get("rationale", ""))
        return ledger, f"写入 {e['id']} proposed"
    if a == "lesson-confirm":
        item = ledger_lesson.confirm_lesson(
            ledger, req.get("candidate", ""), req.get("title", ""),
            req.get("insight", ""), req.get("action_text", ""))
        return ledger, f"确认经验 {item['id']}"
    if a == "lesson-dismiss":
        cand = ledger_lesson.dismiss_lesson(ledger, req.get("candidate", ""),
                                            req.get("reason", ""))
        return ledger, f"驳回候选 {cand['id']}"

    # 目标编排：全部委托给纯函数层，网关只提供身份/CAS/审计/落盘。
    gid = req.get("goal_id", "")
    if a == "goal-create":
        g = goal_ledger.create_goal(
            ledger, goal_id=gid, description=req.get("title", ""),
            success_criteria=req.get("criteria", []),
            max_loops=int(req.get("max_loops", 0)),
            authorized_by=req.get("authorized_by", ""),
            approved_by=req.get("approved_by", ""))
        return ledger, f"创建目标 {g['goal_id']}（预算 {g['max_loops']} 轮）"
    if a == "goal-approve":
        p = goal_ledger.approve_change(ledger, gid, req.get("proposal_id", ""),
                                       approved_by=req.get("approved_by", ""))
        return ledger, f"人批准目标调整 {p['id']}，方向锁重算"
    if a == "goal-reject":
        p = goal_ledger.reject_change(ledger, gid, req.get("proposal_id", ""),
                                      approved_by=req.get("approved_by", ""),
                                      reason=req.get("reason", ""))
        return ledger, f"人驳回目标调整 {p['id']}"
    if a == "goal-advance":
        g = goal_ledger.advance_goal(ledger, gid, actor=actor)
        return ledger, f"推进 {gid} 至 {g['current_loop']}/{g['max_loops']}"
    if a == "goal-achieve":
        goal_ledger.achieve_goal(ledger, gid, actor=actor)
        return ledger, f"目标 {gid} 标记达成"
    if a == "goal-deactivate":
        goal_ledger.deactivate_goal(ledger, gid, actor=actor,
                                    reason=req.get("reason", "超预算未达成"))
        return ledger, f"目标 {gid} 失活：{req.get('reason', '超预算未达成')}"
    if a == "goal-pause":
        goal_ledger.pause_goal(ledger, gid, actor=actor, reason=req.get("reason", "人工暂停"))
        return ledger, f"目标 {gid} 暂停"
    if a == "goal-resume":
        goal_ledger.resume_goal(ledger, gid, actor=actor)
        return ledger, f"目标 {gid} 恢复"
    if a == "goal-propose":
        p = goal_ledger.propose_change(
            ledger, gid, actor=actor,
            original_goal=req.get("original_goal", ""),
            proposed_change=req.get("proposed_change", ""),
            rationale=req.get("rationale", ""), impact=req.get("impact", ""),
            proposed_description=req.get("proposed_description") or None,
            proposed_criteria=req.get("proposed_criteria") or None)
        return ledger, f"提出目标调整 {p['id']}（未改目标本身）"
    raise ValueError(f"动作 {a} 不是网关写入动作")


@contextmanager
def write_lock(target: Path, strict: bool = True):
    """读-判-写原子化。POSIX flock；无 fcntl 时按 E6 诚实边界降级。"""
    if fcntl is None:
        if strict:
            print("[WARN] 当前平台没有 fcntl，写入缺少 OS 级互斥；"
                  "请用单写入者或容器隔离", file=sys.stderr)
        yield
        return
    p = Path(target) / LOCK_NAME
    p.touch(exist_ok=True)
    with p.open("r+") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def status(ledger: dict, gov: Path) -> dict:
    acc = _access(ledger)
    return {"schema": SCHEMA, "command": "status",
            "access_schema": acc.get("schema"), "revision": acc.get("revision"),
            "registry_sha256": registry_sha(gov),
            "current_fingerprint": current_fingerprint(ledger),
            "agents": [{"id": a.get("id"), "role": a.get("role"),
                        "enabled": a.get("enabled"), "scopes": a.get("scopes", [])}
                       for a in acc.get("agents", [])],
            "leases": list(acc.get("leases", [])),
            "audit_entries": len(acc.get("audit", [])),
            "last_audit": (acc.get("audit") or [{}])[-1],
            "roles": {k: list(v) for k, v in ROLE_POLICIES.items()},
            "actions": {k: v["kind"] for k, v in ACTIONS.items()}}


def _load_json_arg(value: str):
    """CLI 的 JSON 参数：空串返回空列表；支持内联 JSON 或 @文件路径。"""
    if not value:
        return []
    raw = Path(value[1:]).read_text(encoding="utf-8") if value.startswith("@") else value
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 参数非法：{exc}") from exc


def request(target: Path, args: argparse.Namespace) -> dict:
    gov = target / "governance"
    ledger = load_ledger(gov)
    req = {
        "agent": args.agent, "action": args.action, "code": args.code or "",
        "expect_fingerprint": args.expect_fingerprint or "",
        "expect_registry_sha": args.expect_registry_sha or "",
        "expect_revision": args.expect_revision,
        "approved_by": args.approved_by or "", "reason": args.reason or "",
        "title": args.title or "", "rationale": args.rationale or "",
        "candidate": args.candidate or "", "insight": args.insight or "",
        "action_text": args.action_text or "", "superseded_by": args.superseded_by or "",
        # 目标编排字段（v2.13.0）：argparse 对未注册属性用 getattr 兜底，兼容旧调用方。
        "goal_id": getattr(args, "goal_id", "") or "",
        "criteria": _load_json_arg(getattr(args, "criteria", "") or "[]"),
        "max_loops": getattr(args, "max_loops", 0) or 0,
        "authorized_by": getattr(args, "authorized_by", "") or "",
        "proposal_id": getattr(args, "proposal_id", "") or "",
        "original_goal": getattr(args, "original_goal", "") or "",
        "proposed_change": getattr(args, "proposed_change", "") or "",
        "impact": getattr(args, "impact", "") or "",
        "proposed_description": getattr(args, "proposed_description", "") or "",
        "proposed_criteria": _load_json_arg(getattr(args, "proposed_criteria", "") or ""),
        "apply": bool(args.apply),
    }
    digest = registry_sha(gov)
    try:
        facts = guard_collect(target, req["expect_fingerprint"] or None)
        guard_result = guard_evaluate(facts)
    except (OSError, ValueError):
        guard_result = None
    result = evaluate(ledger, req, guard_result, digest)

    if args.apply and result["decision"] == "allow":
        spec = ACTIONS[args.action]
        with write_lock(target):
            ledger = load_ledger(gov)  # 锁内重读，避免等待期间的世界变化
            digest2 = registry_sha(gov)
            recheck = evaluate(ledger, req, guard_evaluate(
                guard_collect(target, req["expect_fingerprint"] or None)), digest2)
            if recheck["decision"] != "allow":
                result = recheck
            else:
                before = current_fingerprint(ledger)
                message = "许可已签发（网关不代写）"
                if spec["kind"] == "ledger-write":
                    try:
                        ledger, message = dispatch(ledger, req)
                    except ValueError as exc:
                        result["decision"] = "deny"
                        result["denied_by"] = ["dispatch_rejected"]
                        result["checks"].append({"id": "dispatch_rejected",
                                                 "status": "deny",
                                                 "reason": str(exc), "fix": ""})
                        return _finalize(result, None)
                acc = ledger["access"]
                if spec["code"] and req["code"] and args.action in (
                        "code", "generate", "decide", "claim"):
                    acc["leases"] = [x for x in acc.get("leases", [])
                                     if not (x.get("code") == req["code"]
                                             and x.get("agent") == req["agent"])]
                    acc["leases"].append({"code": req["code"], "agent": req["agent"],
                                          "at": _now(), "ttl_minutes": LEASE_TTL_MINUTES})
                if args.action == "release":
                    acc["leases"] = [x for x in acc.get("leases", [])
                                     if x.get("code") != req["code"]]
                _audit(acc, {"agent": req["agent"], "action": req["action"],
                             "code": req["code"], "reason": req["reason"],
                             "approved_by": req["approved_by"],
                             "registry_sha": digest2,
                             "fingerprint_before": before,
                             "outcome": "applied" if spec["kind"] == "ledger-write"
                                        else "permitted"},
                       fingerprint_after=current_fingerprint(ledger))
                write_ledger(gov, ledger)
                result["message"] = message
                result["audit"] = acc["audit"][-1]
    return _finalize(result, req["apply"])


def _finalize(result: dict, applied: bool | None) -> dict:
    result["applied"] = bool(applied and result["decision"] == "allow")
    return result


def check_definitions() -> list[str]:
    errs: list[str] = []
    if len(ACTIONS) != len(set(ACTIONS)):
        errs.append("动作定义重复")
    for name, spec in ACTIONS.items():
        if spec["kind"] not in ("ledger-write", "permit-only"):
            errs.append(f"{name} 的 kind 非法")
        if spec["kind"] == "ledger-write" and spec["guard"] not in (
                "decide", "lesson", "lifecycle", "claim", "release", "status"):
            errs.append(f"{name} 的 guard 映射不在写入动作集合")
    for role, actions in ROLE_POLICIES.items():
        for a in actions:
            if a not in ACTIONS:
                errs.append(f"角色 {role} 引用了未知动作 {a}")
    for a in LIFECYCLE_ACTIONS:
        if ACTIONS[a]["kind"] != "ledger-write":
            errs.append(f"生命周期动作 {a} 必须由网关亲自写")
    for name in ("decide", "lesson-confirm", "lesson-dismiss"):
        if ACTIONS[name]["kind"] != "ledger-write":
            errs.append(f"决策/经验动作 {name} 必须由网关亲自写")
    return errs


def _render(result: dict) -> str:
    if result.get("command") == "register":
        a = result["agent"]
        return (f"已登记 Agent：{a['id']} [{a['role']}] "
                f"批准人={a['approved_by']} scopes={a['scopes']} "
                f"| applied={result['applied']}")
    if result.get("command") == "status":
        return (f"接入登记：{result['access_schema']} | revision={result['revision']} "
                f"| Agent {len(result['agents'])} | 租约 {len(result['leases'])} "
                f"| 审计 {result['audit_entries']} 条\n"
                f"registry_sha256={result['registry_sha256']}\n"
                f"current_fingerprint={result['current_fingerprint']}\n"
                + "\n".join(f"  {a['id']} [{a['role']}] enabled={a['enabled']}"
                            for a in result["agents"]))
    lines = [f"网关判定：{result['decision'].upper()} | {result['agent']} → "
             f"{result['action']} {result['code']}".rstrip(),
             f"applied={result['applied']}"]
    for c in result["checks"]:
        if c["status"] != "pass":
            lines.append(f"  [{c['status'].upper()}] {c['id']}：{c['reason']}"
                         + (f" → {c['fix']}" if c["fix"] else ""))
    if result["permit"]:
        lines.append("permit：" + json.dumps(result["permit"], ensure_ascii=False))
    if result.get("message"):
        lines.append(result["message"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default=".", help="被治理项目根目录")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    p_status = sub.add_parser("status")
    p_status.add_argument("--json", action="store_true")
    p_reg = sub.add_parser("register")
    p_reg.add_argument("--agent", required=True)
    p_reg.add_argument("--role", required=True)
    p_reg.add_argument("--approved-by", required=True)
    p_reg.add_argument("--scope", action="append", default=[], help="可重复，编码前缀")
    p_reg.add_argument("--apply", action="store_true")
    p_reg.add_argument("--json", action="store_true")
    p_req = sub.add_parser("request")
    p_req.add_argument("--agent", required=True)
    p_req.add_argument("--action", required=True, choices=sorted(ACTIONS))
    p_req.add_argument("--code", default="")
    p_req.add_argument("--expect-fingerprint", default="")
    p_req.add_argument("--expect-registry-sha", default="")
    p_req.add_argument("--expect-revision", type=int, default=None)
    p_req.add_argument("--approved-by", default="")
    p_req.add_argument("--reason", default="")
    p_req.add_argument("--title", default="")
    p_req.add_argument("--rationale", default="")
    p_req.add_argument("--candidate", default="")
    p_req.add_argument("--insight", default="")
    p_req.add_argument("--action-text", default="")
    p_req.add_argument("--superseded-by", default="")
    # 目标编排字段（v2.13.0）
    p_req.add_argument("--goal-id", default="", help="目标 ID（G- 开头）")
    p_req.add_argument("--criteria", default="", help="成功判据 JSON 数组或 @文件")
    p_req.add_argument("--max-loops", type=int, default=0, help="最大循环预算 1-100")
    p_req.add_argument("--authorized-by", default="", help="目标授权的批准人")
    p_req.add_argument("--proposal-id", default="", help="调整提议 ID（P- 开头）")
    p_req.add_argument("--original-goal", default="", help="提议：原目标")
    p_req.add_argument("--proposed-change", default="", help="提议：建议变更")
    p_req.add_argument("--impact", default="", help="提议：影响")
    p_req.add_argument("--proposed-description", default="", help="提议：新描述（仅人批准后生效）")
    p_req.add_argument("--proposed-criteria", default="", help="提议：新判据 JSON")
    p_req.add_argument("--apply", action="store_true")
    p_req.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.command == "check":
        errs = check_definitions()
        if errs:
            print("\n".join(errs), file=sys.stderr)
            return 2
        print(f"网关定义自检通过：{len(ROLE_POLICIES)} 个角色 / "
              f"{len(ACTIONS)} 个动作 / {sum(1 for a in ACTIONS.values() if a['kind'] == 'ledger-write')} 个网关写入动作")
        return 0

    target = Path(args.target).expanduser().resolve()
    gov = target / "governance"
    try:
        ledger = load_ledger(gov)
    except ValueError as exc:
        print(f"拒绝：{exc}", file=sys.stderr)
        return 1

    if args.command == "status":
        result = status(ledger, gov)
        rc = 0
    elif args.command == "register":
        if not args.apply:
            print("注册默认 dry-run：加 --apply 才写入（需人工批准）")
            return 0
        try:
            item = register(ledger, args.agent, args.role, args.approved_by, args.scope)
        except ValueError as exc:
            print(f"拒绝：{exc}", file=sys.stderr)
            return 1
        write_ledger(gov, ledger)
        result = {"schema": SCHEMA, "command": "register", "applied": True,
                  "agent": item}
        rc = 0
    else:
        result = request(target, args)
        rc = 0 if result["decision"] == "allow" else 1

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
          if args.json else _render(result))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
