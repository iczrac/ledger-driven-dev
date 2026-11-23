#!/usr/bin/env python3
"""场景预检：在任何写入前，先判断「此时此地是否允许这个动作」。

第一性原理分层
--------------
verify_ledger.py 检查账本**内部**自洽（31 条不变量）；
本脚本检查**外部/时间/并发/生命周期**前置条件。两者不重叠：
一个回答「账本有没有坏」，一个回答「现在能不能动它」。

六条公理
--------
A1 状态完备   必须能回答：在哪 / 去哪 / 谁在改 / 凭什么 / 谁批准
A2 证据有效   结论来自可复算证据，且证据必须**对当前源码有效**
A3 单点写入   同一事实只有一个写入点，写入者权限由路由确定
A4 时间可逆   历史不可篡改，且能检测并发覆盖与执行中断
A5 未知即停止 版本、路径、完整性存疑时 fail-closed
A6 边界闭合   进入 / 冻结 / 归档 / 移交 / 退役 / 失效都有明确出口

用法
----
    python3 scripts/scenario_guard.py --target . --json
    python3 scripts/scenario_guard.py --target . --expect-fingerprint abcd... --strict
    python3 scripts/scenario_guard.py --target . --test-report governance/test_report.json

输出 schema: scenario-preflight/1。只读、确定性、仅标准库。
退出码：0=可读；2=输入错误或 --strict 下存在 block。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

SCHEMA = "scenario-preflight/1"
SUPPORTED_LEDGER_VERSIONS = {"1.0"}
AXIOMS = {
    "A1": "状态完备", "A2": "证据有效", "A3": "单点写入",
    "A4": "时间可逆", "A5": "未知即停止", "A6": "边界闭合",
}
WRITE_ACTIONS = ["bootstrap", "generate", "decide", "code", "lesson",
                 "lifecycle", "claim", "release", "claim_verified"]
READ_ACTIONS = ["status", "discover", "verify"]
ALL_ACTIONS = READ_ACTIONS + WRITE_ACTIONS

# Windows 盘符前不能紧邻字母/数字/URI scheme 字符，且后面不能再跟斜杠：
# 否则 file:// 的 "e:/"、https:// 的 "s:/" 会被误判成绝对路径（假冻结）。
ABS_PATH_RE = re.compile(
    r"(?:/Users/|/home/|/private/var/|(?<![A-Za-z0-9+.\-])[A-Za-z]:[\\/](?![/]))"
)
EMBED_RE = re.compile(r"const EMBED = (\{.*?\});\nlet DATA", re.S)


def _json_state(path: Path) -> tuple[str, dict]:
    if not path.exists():
        return "absent", {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return "corrupt", {}
    if not isinstance(data, dict):
        return "corrupt", {}
    return "ok", data


def _active_cap_codes(ledger: dict) -> set[str]:
    out: set[str] = set()
    for p in ledger.get("capability_model", {}).get("projects", []):
        for m in p.get("modules", []):
            for c in m.get("caps", []):
                if c.get("code"):
                    out.add(c["code"])
    return out


def _board_synced(board: Path, ledger: dict) -> bool | None:
    if not board.exists():
        return None
    try:
        m = EMBED_RE.search(board.read_text(encoding="utf-8"))
        if not m:
            return False
        return json.loads(m.group(1)) == ledger
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False


def _binding_fresh(report: dict, target: Path, proj_rel: str) -> tuple[bool | None, str]:
    """真实重算报告的源码绑定摘要；与生成器 check_freshness 同契约。

    只检查「有没有绑定字段」是假检查：必须逐文件重算 sha256，
    才能在预检阶段就拦下「测试通过后改了源码」的过期证据。
    """
    binding = report.get("evidence_binding") or {}
    inputs = binding.get("inputs") or []
    if binding.get("algorithm") != "sha256-files-v1" or not inputs:
        return None, "unbound"
    for item in inputs:
        rel = str(item.get("path", ""))
        want = str(item.get("sha256", ""))
        if not rel or not want:
            return False, "invalid-input"
        cands = [target / rel]
        if proj_rel:
            cands.append(target / proj_rel / rel)
        hit = next((c for c in cands if c.is_file()), None)
        if hit is None:
            same_name = [c for c in target.rglob(Path(rel).name) if c.is_file()]
            if len(same_name) == 1:
                hit = same_name[0]
        if hit is None:
            return False, "missing:" + Path(rel).name
        if hashlib.sha256(hit.read_bytes()).hexdigest() != want:
            return False, "changed:" + Path(rel).name
    return True, "fresh"


def _git_facts(target: Path) -> dict:
    # 项目根常在 git 仓库的子目录（monorepo），向上找最近的 .git
    git = next((d / ".git" for d in (target, *target.parents) if (d / ".git").exists()), None)
    if git is None:
        return {"present": False, "shallow": False}
    shallow = (git / "shallow").exists()
    if not shallow:
        try:
            r = subprocess.run(["git", "-C", str(target), "rev-parse",
                                "--is-shallow-repository"],
                               capture_output=True, text=True, timeout=3)
            shallow = r.returncode == 0 and r.stdout.strip() == "true"
        except (OSError, subprocess.SubprocessError):
            pass
    return {"present": True, "shallow": shallow}


def collect(target: Path, expect_fingerprint: str | None = None,
            test_report: str | None = None, max_files: int = 2000) -> dict:
    """只读采集场景事实；不写任何文件。"""
    gov = target / "governance"
    ledger_state, ledger = _json_state(gov / "DECISION_LEDGER.json")
    registry_state, registry = _json_state(gov / "registry.json")
    if ledger_state == "ok":
        ledger_state = "active" if (ledger.get("entries") or
                                    ledger.get("capability_model")) else "empty"

    lifecycle = ledger.get("lifecycle", {}) if isinstance(ledger.get("lifecycle"), dict) else {}
    lc_state = str(lifecycle.get("state", "active"))
    if lc_state not in ("active", "frozen", "archived"):
        lc_state = "active"
    fingerprint = (ledger.get("capability_model", {})
                   .get("history", {}).get("current_fingerprint"))

    rp = Path(test_report) if test_report else gov / "test_report.json"
    if not rp.is_absolute():
        rp = target / rp if test_report else rp
    report_state, report = _json_state(rp)
    has_binding = (bool(report.get("evidence_binding", {}).get("inputs"))
                   if report_state == "ok" else False)
    fresh, fresh_detail = None, "unbound"
    if report_state == "ok" and has_binding:
        proj_rel = str(registry.get("project", {}).get("root", "")).strip("/")
        fresh, fresh_detail = _binding_fresh(report, target, proj_rel)
    report_facts = {
        "path": rp.name,
        "present": report_state == "ok",
        "overall": report.get("overall") if report_state == "ok" else None,
        "generated_at": report.get("generated_at", "") if report_state == "ok" else "",
        "has_binding": has_binding,
        "declared_fresh": fresh,
        "fresh_detail": fresh_detail,
    }
    if report_state == "corrupt":
        report_facts["present"] = False

    retired = ledger.get("retired_caps", [])
    retired_codes = {x.get("code") for x in retired if isinstance(x, dict) and x.get("code")}
    active_codes = _active_cap_codes(ledger)
    claims = ledger.get("execution", {}).get("claims", []) if isinstance(
        ledger.get("execution"), dict) else []

    texts = ""
    for p in (gov / "DECISION_LEDGER.json", rp):
        try:
            texts += p.read_text(encoding="utf-8") if p.is_file() else ""
        except (OSError, UnicodeDecodeError):
            pass
    absolute_paths = sorted(set(ABS_PATH_RE.findall(texts)))[:5]

    scanned, truncated = 0, False
    for root, dirs, files in os.walk(target):
        dirs[:] = sorted(d for d in dirs if d not in {
            ".git", "node_modules", "__pycache__", ".venv", "venv", ".workbuddy"})
        for name in files:
            scanned += 1
            if scanned >= max_files:
                truncated = True
                break
        if truncated:
            break

    template_sync = None
    tpl = target / "templates" / "build_capability_model.py"
    demo = target / "examples" / "demo-shop" / "governance" / "build_capability_model.py"
    if tpl.exists() and demo.exists():
        template_sync = tpl.read_bytes() == demo.read_bytes()

    mode = lc_state if lc_state != "active" else None
    if mode is None:
        if ledger_state == "corrupt" or registry_state == "corrupt":
            mode = "corrupt"
        elif ledger_state in ("active", "empty") and registry_state == "ok":
            mode = "governed"
        elif ledger_state != "absent" or registry_state == "ok":
            mode = "partial"
        elif scanned:
            mode = "brownfield"
        else:
            mode = "greenfield"

    return {
        "mode": mode,
        "ledger_state": ledger_state,
        "registry_state": registry_state,
        "ledger_version": ledger.get("ledger_version"),
        "lifecycle": {
            "state": lc_state,
            "approved_by": lifecycle.get("approved_by", ""),
            "reason": lifecycle.get("reason", ""),
            "log_entries": len(lifecycle.get("log", []) or []),
        },
        "current_fingerprint": fingerprint,
        "expect_fingerprint": expect_fingerprint,
        "report": report_facts,
        "board_synced": _board_synced(gov / "index.html", ledger),
        "git": _git_facts(target),
        "retired": {"codes": sorted(retired_codes),
                    "conflicts": sorted(retired_codes & active_codes)},
        "claims": [c for c in claims if isinstance(c, dict)],
        "hygiene": {"absolute_paths": absolute_paths},
        "template_sync": template_sync,
        "scan": {"files": scanned, "truncated": truncated},
        "registry_modules": len(registry.get("modules", [])) if registry_state == "ok" else 0,
    }


def evaluate(facts: dict, stale_minutes: int = 120) -> dict:
    """纯函数：facts -> 预检结论。测试可直接构造 facts，不依赖文件系统。"""
    checks: list[dict] = []

    def add(cid: str, axiom: str, status: str, reason: str,
            fix: str, blocks: list[str] | None = None) -> None:
        checks.append({"id": cid, "axiom": axiom, "status": status,
                       "reason": reason, "fix": fix, "blocks": blocks or []})

    if facts["ledger_state"] == "corrupt":
        add("ledger_parseable", "A5", "block", "账本无法解析，任何写入都会污染唯一事实源",
            "先备份，再人工修复 JSON，然后跑 verify_ledger.py", WRITE_ACTIONS)
    else:
        add("ledger_parseable", "A5", "pass", "账本可读", "")

    ver = facts.get("ledger_version")
    if ver is None:
        add("schema_compat", "A5", "warn", "账本未标注 ledger_version，按 1.0 兼容处理",
            "由 init_project.py 或生成器补写 ledger_version")
    elif str(ver) not in SUPPORTED_LEDGER_VERSIONS:
        add("schema_compat", "A5", "block", f"账本版本 {ver} 不在支持集合 "
            f"{sorted(SUPPORTED_LEDGER_VERSIONS)}，跨版本直写会破坏历史语义",
            "先导出账本快照，运行迁移 dry-run 并人工确认", WRITE_ACTIONS)
    else:
        add("schema_compat", "A5", "pass", f"账本版本 {ver} 与工具链兼容", "")

    state = facts["lifecycle"]["state"]
    if state == "frozen":
        add("lifecycle_writable", "A6", "block", "项目处于冻结态（发布窗口/审计期）",
            "由 lifecycle.py unfreeze --approved-by <人> 解冻；AI 不得自行解冻",
            [a for a in WRITE_ACTIONS if a != "lifecycle"])
        if not facts["lifecycle"]["approved_by"]:
            add("approval_gate", "A1", "warn", "冻结记录缺少批准人",
                "补记 approved_by，满足审计取证")
        else:
            add("approval_gate", "A1", "pass", "冻结有批准人记录", "")
    elif state == "archived":
        add("lifecycle_writable", "A6", "block", "项目已归档，为不可写终态",
            "需要继续开发请复制出新项目，不要解冻归档账本", WRITE_ACTIONS)
        add("approval_gate", "A1", "pass", "归档要求过人工批准", "")
    else:
        add("lifecycle_writable", "A6", "pass", "项目处于可写 active 态", "")
        add("approval_gate", "A1", "pass", "无需批准门", "")

    rep = facts["report"]
    if not rep["present"]:
        add("evidence_bound", "A2", "warn", "没有实测报告，全部能力只能是 declared",
            "运行 scripts/run_tests.py 生成报告")
    elif rep["overall"] != "pass":
        add("evidence_bound", "A2", "block", "实测报告整体未通过",
            "修复失败用例后重跑报告", ["claim_verified"])
    elif not rep["has_binding"]:
        add("evidence_bound", "A2", "warn", "报告未绑定源码摘要，无法证明它对应当前代码",
            "用 v0.8.0+ 的 run_tests.py 重跑；或对生成器加 --strict-evidence",
            ["claim_verified"] if rep["declared_fresh"] is False else [])
    else:
        add("evidence_bound", "A2", "pass", "报告已绑定源码摘要", "")

    if rep.get("declared_fresh") is False:
        add("evidence_fresh", "A2", "block", "报告生成后源码/测试已变化，verified 是过期证据",
            "重跑 run_tests.py 并重新生成账本", ["claim_verified"])
    elif rep["has_binding"]:
        add("evidence_fresh", "A2", "pass", "报告摘要与当前源码一致", "")
    else:
        add("evidence_fresh", "A2", "warn", "新鲜度无法判定（报告无绑定摘要）",
            "重跑 run_tests.py")

    exp = facts.get("expect_fingerprint")
    cur = facts.get("current_fingerprint")
    if exp and exp != cur:
        add("concurrent_write", "A4", "block",
            f"读取时指纹 {exp}，当前 {cur}：期间有人写入过，继续写会静默覆盖",
            "重新读取账本、合并变更后再带新指纹重试（CAS）",
            ["generate", "decide", "code", "lesson", "lifecycle", "claim", "release"])
    elif exp:
        add("concurrent_write", "A4", "pass", "指纹未变，无并发覆盖", "")
    else:
        add("concurrent_write", "A4", "warn", "未提供 --expect-fingerprint，无法检测读后写漂移",
            "并发/多 Agent 场景请始终传入读取时指纹")

    conflicts = facts["retired"]["conflicts"]
    if conflicts:
        add("retired_caps_consistent", "A1", "block",
            f"已退役编码仍出现在活跃能力模型：{', '.join(conflicts)}",
            "同步从 registry.json 移除该能力，再重跑生成器", ["generate"])
    else:
        add("retired_caps_consistent", "A1", "pass", "退役记录与活跃能力无冲突", "")

    stale_claims = []
    now = datetime.now()
    for c in facts.get("claims", []):
        try:
            at = datetime.fromisoformat(str(c.get("at", "")))
            if now - at > timedelta(minutes=stale_minutes):
                stale_claims.append(c.get("code", ""))
        except ValueError:
            stale_claims.append(c.get("code", ""))
    if stale_claims:
        add("execution_resumable", "A4", "warn",
            f"存在超过 {stale_minutes} 分钟未释放的任务锁：{', '.join(stale_claims)}",
            "确认执行者状态后 lifecycle.py release，避免任务永久卡住")
    else:
        add("execution_resumable", "A4", "pass", "无陈旧任务锁", "")

    if facts["board_synced"] is False:
        add("board_synced", "A3", "warn", "看板 EMBED 与账本不一致",
            "重跑生成器同步看板")
    else:
        add("board_synced", "A3", "pass", "看板与账本一致（或无看板）", "")

    git = facts["git"]
    if not git["present"]:
        add("git_history", "A4", "warn", "目录不是 git 仓库，变更无法回连提交",
            "git init 并纳入治理；trace_git.py 会在非 git 场景退出 2")
    elif git.get("shallow"):
        add("git_history", "A4", "warn", "浅克隆历史不完整，git 追踪结论可能缺样本",
            "CI 中使用 fetch-depth: 0")
    else:
        add("git_history", "A4", "pass", "git 历史可用", "")

    if facts["hygiene"]["absolute_paths"]:
        add("path_hygiene", "A5", "block", "账本/报告残留机器绝对路径",
            "归一为相对路径后重新生成", WRITE_ACTIONS)
    else:
        add("path_hygiene", "A5", "pass", "无绝对路径泄露", "")

    if facts.get("template_sync") is False:
        add("template_sync", "A5", "warn", "模板与示例副本漂移",
            "运行同步脚本；check.sh 会把这当作门禁失败")
    elif facts.get("template_sync") is True:
        add("template_sync", "A5", "pass", "模板与副本一致", "")
    else:
        add("template_sync", "A5", "pass", "本仓库不适用模板同步", "")

    if facts["scan"]["truncated"]:
        add("scan_complete", "A5", "warn", f"扫描达到 {facts['scan']['files']} 文件上限",
            "提高 --max-files 后重跑，不要据此声称全量覆盖")
    else:
        add("scan_complete", "A5", "pass", "扫描未截断", "")

    blocked = sorted({a for c in checks for a in c["blocks"] if c["status"] == "block"})
    allowed = [a for a in ALL_ACTIONS if a not in blocked]
    mode = facts["mode"]
    hint = {
        "corrupt": ("evidence-auditor", "先审计修复账本", True),
        "frozen": ("ledger-steward", "冻结期只允许只读与经批准解冻", True),
        "archived": ("ledger-steward", "归档终态，只允许打包与取证", True),
        "brownfield": ("project-archaeologist", "先只读盘点再无损接入", False),
        "greenfield": ("greenfield-architect", "建立最小治理骨架", False),
        "partial": ("ledger-steward", "补齐缺失的单一手写清单", False),
        "governed": ("loop-executor" if "code" in allowed else "evidence-auditor",
                     "进入证据补齐循环" if "code" in allowed else "先处理阻塞项", False),
    }.get(mode, ("evidence-auditor", "状态未识别，先取证", True))

    counts = {s: sum(1 for c in checks if c["status"] == s)
              for s in ("pass", "warn", "block")}
    return {
        "schema": SCHEMA,
        "facts": facts,
        "checks": checks,
        "summary": {**counts, "total": len(checks),
                    "writable": not any(a in blocked for a in
                                        ("generate", "decide", "code", "lesson"))},
        "blocked_actions": blocked,
        "allowed_actions": allowed,
        "route_hint": {"expert": hint[0], "reason": hint[1], "blocked": hint[2] or bool(blocked)},
        "axioms": AXIOMS,
    }


def render(result: dict) -> str:
    s, f = result["summary"], result["facts"]
    lines = [
        f"场景预检：{f['mode']} | ledger={f['ledger_state']} "
        f"registry={f['registry_state']} | 生命周期={f['lifecycle']['state']}",
        f"结果：{s['pass']} pass / {s['warn']} warn / {s['block']} block "
        f"（共 {s['total']} 项）· 可写={s['writable']}",
    ]
    for c in result["checks"]:
        if c["status"] != "pass":
            lines.append(f"  [{c['status'].upper():5}] {c['id']}（{c['axiom']}）：{c['reason']}")
            if c["fix"]:
                lines.append(f"          → {c['fix']}")
    if result["blocked_actions"]:
        lines.append("被阻止的动作：" + ", ".join(result["blocked_actions"]))
    lines.append(f"建议负责人：{result['route_hint']['expert']} —— {result['route_hint']['reason']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default=".", help="目标项目根目录")
    ap.add_argument("--expect-fingerprint", help="读取账本时的 current_fingerprint（CAS）")
    ap.add_argument("--test-report", help="测试报告路径（默认 governance/test_report.json）")
    ap.add_argument("--max-files", type=int, default=2000)
    ap.add_argument("--stale-minutes", type=int, default=120, help="任务锁陈旧阈值")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="存在 block 时返回 2")
    args = ap.parse_args(argv)

    target = Path(args.target).expanduser().resolve()
    if not target.is_dir():
        print(f"目标目录不存在：{args.target}", file=sys.stderr)
        return 2
    facts = collect(target, args.expect_fingerprint, args.test_report, args.max_files)
    result = evaluate(facts, args.stale_minutes)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render(result))
    return 2 if args.strict and result["summary"]["block"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
