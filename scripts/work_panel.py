#!/usr/bin/env python3
"""节点工作台：把 TODO / issue / 测试结果绑定到模块与组件，并保持单一事实源。

第一性原理
----------
v1.1.0 的看板是「决策账本 + 能力地图 + 历史/经验」浏览器，`next_queue`
虽有任务卡但看板没渲染，`test_report.json` 只有汇总徽章，没有逐用例明细，
更没有「这个模块现在有什么待办、什么缺陷、哪些测试挂了」。
于是一个项目负责人看完看板，仍然要回到聊天记录、issue 列表和 CI 日志里找答案。

v1.2.0 把节点级工作态压回同一份账本：
  - `work_items`：账本内数组，id / kind(todo|issue) / scope(项目|模块|能力编码) /
    status(open|doing|done|blocked) / severity / owner / refs。唯一写入点是本脚本；
  - `test_results`：`governance/test_report.json` 的**可验证投影**，用 source_sha256
    绑定原始报告，只保留看板需要的字段，不含生成时间等易变数据；
  - 派生聚合不在账本落盘：`nodes` 命令与看板 JS 从上面两份数据按 scope 复算，
    因此不产生第三份需要同步的事实。

scope 语义
----------
    PROJECT                 全局，出现在所有节点
    DEMO                    项目级
    DEMO.CORE               模块级（含其下所有能力点）
    DEMO.CORE.ORDER.01      能力点级（四段式编码）

纪律
----
- `add` / `close` / `sync-tests` 默认 dry-run，写盘必须 `--apply --approved-by <人>`；
- 写入同时同步看板 EMBED（走 ledger_io.write_ledger，不单独改 HTML）；
- 不含时间戳；work item id 由现有最大序号派生，保证可复算；
- `nodes` 是只读取证，可被 Agent 直接消费，也可被 CI 用来判断节点健康度。

用法
----
    python3 scripts/work_panel.py --target P check --json
    python3 scripts/work_panel.py --target P nodes --json
    python3 scripts/work_panel.py --target P sync-tests --apply --approved-by 张三 --json
    python3 scripts/work_panel.py --target P add --kind todo --scope DEMO.CORE.ORDER.01 \
        --title "补边界用例" --apply --approved-by 张三 --json
    python3 scripts/work_panel.py --target P close --id W-TODO-001 \
        --apply --approved-by 张三 --json

退出码：0 成功；1 被拒绝 / 校验失败；2 输入错误。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ledger_io import load_ledger, write_ledger  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_CHECK = "work-panel-check/1"
SCHEMA_NODES = "node-work-summary/1"
SCHEMA_TEST_RESULTS = "node-test-results/1"
SCHEMA_WORK_ITEMS = "work-items/1"
SCHEMA_ACTION = "work-panel-action/1"
REPORT_REL = "governance/test_report.json"
KINDS = {"todo", "issue"}
STATUSES = {"open", "doing", "done", "blocked"}
SEVERITIES = {"low", "med", "high"}
CASE_STATUSES = {"pass", "fail", "error", "skip"}
CAP_RE = re.compile(r"^[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9]*\.\d{2}$")


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def cap_index(ledger: dict) -> dict[str, dict]:
    """能力编码 → 所属项目/模块、单测路径、证据分层。只读取证。"""
    out: dict[str, dict] = {}
    cm = ledger.get("capability_model") or {}
    for p in cm.get("projects", []):
        pcode = p.get("code", "")
        for m in p.get("modules", []):
            mcode = m.get("code", "")
            for c in m.get("caps", []):
                di = c.get("doc_index") or {}
                paths = []
                for x in (di.get("unit_tests") or []):
                    paths.append(x.get("path") if isinstance(x, dict) else str(x))
                out[c.get("code", "")] = {
                    "project": pcode, "module": mcode,
                    "unit_tests": sorted({x for x in paths if x}),
                    "tier": c.get("evidence_tier", "declared"),
                    "level": c.get("level", 0),
                    "name": c.get("name", ""),
                }
    return out


def valid_scopes(ledger: dict) -> set[str]:
    idx = cap_index(ledger)
    scopes = {"PROJECT"}
    for code, info in idx.items():
        scopes.add(code)
        scopes.add(info["module"])
        scopes.add(info["project"])
    return scopes


def scope_applies(scope: str, code: str) -> bool:
    """模块/项目级工作项向下覆盖到能力点。"""
    if scope == "PROJECT" or scope == code:
        return True
    return bool(code.startswith(scope + "."))


def _norm_path(p: str) -> str:
    return str(p).replace("\\", "/").lstrip("./")


def cases_for_codes(cases: list[dict], paths: set[str]) -> list[dict]:
    """按单测路径把逐用例测试结果归到节点。"""
    if not paths:
        return []
    norm = {_norm_path(x) for x in paths}
    hits = []
    for c in cases:
        f = _norm_path(str(c.get("file", "")))
        if any(f == n or f.endswith("/" + n) or n.endswith("/" + f) for n in norm):
            hits.append(c)
    return hits


def validate(ledger: dict, governance_dir: Path | None = None) -> list[str]:
    """账本内工作态的自洽校验（同时被 verify_ledger.py 的 3 条不变量调用）。"""
    errs: list[str] = []
    items = ledger.get("work_items") or []
    if not isinstance(items, list):
        return ["work_items 必须是数组"]
    scopes = valid_scopes(ledger)
    ids = [x.get("id") for x in items if isinstance(x, dict)]
    if len(ids) != len(set(ids)) or any(not x for x in ids):
        errs.append("work_items 的 id 必须唯一且非空")
    decisions = {e.get("id") for e in ledger.get("entries", [])}
    caps = set(cap_index(ledger))
    for x in items:
        if not isinstance(x, dict):
            errs.append("work_items 含非对象元素")
            continue
        wid = x.get("id", "?")
        if x.get("kind") not in KINDS:
            errs.append(f"{wid}: kind 必须是 todo 或 issue")
        if x.get("status") not in STATUSES:
            errs.append(f"{wid}: status 非法")
        if x.get("severity", "med") not in SEVERITIES:
            errs.append(f"{wid}: severity 非法")
        if not x.get("title"):
            errs.append(f"{wid}: 缺少 title")
        if x.get("scope") not in scopes:
            errs.append(f"{wid}: scope 无法解析（{x.get('scope')}）")
        for r in (x.get("refs") or []):
            if not isinstance(r, dict):
                errs.append(f"{wid}: refs 元素必须是对象")
                continue
            kind, value = r.get("kind"), str(r.get("value", ""))
            if kind == "decision" and value not in decisions:
                errs.append(f"{wid}: 引用了不存在的决策 {value}")
            elif kind == "capability" and value not in caps:
                errs.append(f"{wid}: 引用了不存在的能力 {value}")
            elif kind not in ("decision", "capability", "path"):
                errs.append(f"{wid}: 未知引用类型 {kind}")

    tr = ledger.get("test_results")
    if tr is not None:
        if not isinstance(tr, dict) or tr.get("schema") != SCHEMA_TEST_RESULTS:
            errs.append("test_results 的 schema 不正确")
        else:
            cases = tr.get("cases") or []
            if not isinstance(cases, list):
                errs.append("test_results.cases 必须是数组")
            else:
                for c in cases:
                    if not isinstance(c, dict) or c.get("status") not in CASE_STATUSES:
                        errs.append("test_results 含非法用例状态")
                s = tr.get("summary") or {}
                if s.get("total") != len(cases):
                    errs.append("test_results.summary.total 与 cases 数量不一致")
            if governance_dir:
                report = governance_dir / "test_report.json"
                if report.is_file() and tr.get("source_sha256") != _sha256_file(report):
                    errs.append("test_results.source_sha256 与当前测试报告不一致（需 sync-tests）")
    return errs


def test_results_from_report(governance_dir: Path) -> dict | None:
    """从机器报告生成确定性投影；不含 generated_at / raw_tail。"""
    report = governance_dir / "test_report.json"
    if not report.is_file():
        return None
    raw = report.read_bytes()
    try:
        d = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    cases = [{"id": c.get("id", ""), "file": c.get("file", ""),
              "status": c.get("status", ""), "seconds": c.get("seconds", 0)}
             for c in d.get("cases", []) if isinstance(c, dict)]
    return {
        "schema": SCHEMA_TEST_RESULTS,
        "source": REPORT_REL,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "overall": d.get("overall", "fail"),
        "summary": dict(d.get("summary") or {}),
        "cases": cases,
        "note": "test_report.json 的只读投影；账本内不复制生成时间与日志尾部",
    }


def nodes(ledger: dict) -> dict:
    """按项目 / 模块 / 能力点复算工作态与健康度（不落盘）。"""
    idx = cap_index(ledger)
    items = ledger.get("work_items") or []
    tr = ledger.get("test_results") or {}
    cases = tr.get("cases") or []
    freshness = ((ledger.get("capability_model") or {}).get("summary") or {}).get(
        "evidence_freshness", "unbound")

    def summarize(scope: str, codes: list[str], tier: str = "") -> dict:
        hit = [x for x in items if isinstance(x, dict)
               and any(scope_applies(str(x.get("scope", "")), c) for c in codes)]
        open_todo = [x for x in hit if x.get("kind") == "todo"
                     and x.get("status") in ("open", "doing")]
        issues = [x for x in hit if x.get("kind") == "issue"
                  and x.get("status") != "done"]
        blocked = [x for x in issues if x.get("status") == "blocked"]
        paths = {p for c in codes for p in idx.get(c, {}).get("unit_tests", [])}
        tc = cases_for_codes(cases, paths)
        failed = [c for c in tc if c.get("status") in ("fail", "error")]
        declared = any(idx.get(c, {}).get("tier") == "declared" for c in codes)
        penalty = (20 * len(blocked) + 8 * (len(issues) - len(blocked))
                   + 15 * len(failed) + (15 if freshness != "fresh" else 0)
                   + (10 if declared else 0))
        return {
            "scope": scope,
            "todo_open": len(open_todo),
            "issues_open": len(issues),
            "issues_blocked": len(blocked),
            "tests_total": len(tc),
            "tests_passed": len(tc) - len(failed),
            "tests_failed": len(failed),
            "declared": declared,
            "health": max(0, 100 - penalty),
        }

    out: list[dict] = []
    by_project: dict[str, list[str]] = {}
    by_module: dict[str, list[str]] = {}
    for code, info in idx.items():
        by_project.setdefault(info["project"], []).append(code)
        by_module.setdefault(info["module"], []).append(code)
    all_codes = list(idx)
    out.append(summarize("PROJECT", all_codes))
    for pcode in sorted(by_project):
        out.append(summarize(pcode, by_project[pcode]))
    for mcode in sorted(by_module):
        out.append(summarize(mcode, by_module[mcode]))
    for code in sorted(idx):
        out.append(summarize(code, [code], idx[code]["tier"]))
    return {"schema": SCHEMA_NODES, "evidence_freshness": freshness,
            "work_items": len(items), "test_cases": len(cases),
            "nodes": out,
            "note": "派生结果，不入账本；看板 JS 用同一规则实时复算"}


def _next_id(items: list[dict], kind: str) -> str:
    prefix = f"W-{kind.upper()}-"
    nums = [int(x["id"][len(prefix):]) for x in items
            if isinstance(x, dict) and isinstance(x.get("id"), str)
            and x["id"].startswith(prefix) and x["id"][len(prefix):].isdigit()]
    return f"{prefix}{(max(nums) + 1) if nums else 1:03d}"


def check(target: Path) -> dict:
    target = Path(target)
    gov = target / "governance"
    try:
        ledger = load_ledger(gov)
    except ValueError as exc:
        return {"schema": SCHEMA_CHECK, "ok": False, "errors": [str(exc)]}
    errs = validate(ledger, gov)
    items = ledger.get("work_items") or []
    tr = ledger.get("test_results") or {}
    return {"schema": SCHEMA_CHECK, "ok": not errs, "errors": errs,
            "work_items": len(items), "test_cases": len(tr.get("cases") or []),
            "nodes": len(nodes(ledger)["nodes"])}


def sync_tests(target: Path, *, approved_by: str = "", apply: bool = False) -> dict:
    target = Path(target)
    gov = target / "governance"
    tr = test_results_from_report(gov)
    if tr is None:
        raise ValueError(f"找不到可读的测试报告：{REPORT_REL}")
    ledger = load_ledger(gov)
    current = ledger.get("test_results")
    same = current == tr
    if not apply:
        return {"schema": SCHEMA_ACTION, "action": "sync-tests", "mode": "dry-run",
                "noop": same, "cases": len(tr["cases"]),
                "source_sha256": tr["source_sha256"],
                "message": "只读预演；写盘需 --apply --approved-by <人>"}
    if not approved_by:
        raise ValueError("同步测试结果必须提供 --approved-by（人工批准）")
    if same:
        return {"schema": SCHEMA_ACTION, "action": "sync-tests", "mode": "apply",
                "noop": True, "cases": len(tr["cases"]),
                "message": "投影已与当前报告一致，无需写入"}
    ledger["test_results"] = tr
    write_ledger(gov, ledger)
    return {"schema": SCHEMA_ACTION, "action": "sync-tests", "mode": "apply",
            "noop": False, "approved_by": approved_by, "cases": len(tr["cases"]),
            "source_sha256": tr["source_sha256"],
            "message": "测试结果投影已写回账本并同步看板"}


def add_item(target: Path, *, kind: str, scope: str, title: str, detail: str = "",
             severity: str = "med", owner: str = "", refs: list[str] | None = None,
             approved_by: str = "", apply: bool = False) -> dict:
    if kind not in KINDS:
        raise ValueError("kind 必须是 todo 或 issue")
    if severity not in SEVERITIES:
        raise ValueError("severity 必须是 low / med / high")
    if not title:
        raise ValueError("title 不能为空")
    target = Path(target)
    gov = target / "governance"
    ledger = load_ledger(gov)
    if scope not in valid_scopes(ledger):
        raise ValueError(f"scope 无法解析：{scope}")
    parsed_refs = []
    for r in refs or []:
        if ":" in r:
            k, v = r.split(":", 1)
        else:
            k, v = ("decision" if re.fullmatch(r"[A-Z]-\d{3}", r) else "path"), r
        parsed_refs.append({"kind": k, "value": v})
    items = ledger.setdefault("work_items", [])
    item = {"id": _next_id(items, kind), "kind": kind, "scope": scope,
            "status": "open", "severity": severity, "title": title,
            "detail": detail, "owner": owner, "refs": parsed_refs}
    if not apply:
        return {"schema": SCHEMA_ACTION, "action": "add", "mode": "dry-run",
                "item": item, "message": "只读预演；写盘需 --apply --approved-by <人>"}
    if not approved_by:
        raise ValueError("新增工作项必须提供 --approved-by（人工批准）")
    errs = validate({**ledger, "work_items": items + [item]}, gov)
    if errs:
        raise ValueError("工作项不自洽：" + "；".join(errs[:3]))
    items.append(item)
    write_ledger(gov, ledger)
    return {"schema": SCHEMA_ACTION, "action": "add", "mode": "apply",
            "approved_by": approved_by, "item": item,
            "message": "工作项已写回账本并同步看板"}


def close_item(target: Path, *, item_id: str, approved_by: str = "",
               apply: bool = False) -> dict:
    target = Path(target)
    gov = target / "governance"
    ledger = load_ledger(gov)
    items = ledger.get("work_items") or []
    item = next((x for x in items if isinstance(x, dict) and x.get("id") == item_id), None)
    if item is None:
        raise ValueError(f"找不到工作项 {item_id}")
    if not apply:
        return {"schema": SCHEMA_ACTION, "action": "close", "mode": "dry-run",
                "item": item, "message": "只读预演；写盘需 --apply --approved-by <人>"}
    if not approved_by:
        raise ValueError("关闭工作项必须提供 --approved-by（人工批准）")
    item["status"] = "done"
    item["closed_by"] = approved_by
    write_ledger(gov, ledger)
    return {"schema": SCHEMA_ACTION, "action": "close", "mode": "apply",
            "approved_by": approved_by, "item": item,
            "message": "工作项已关闭并同步看板"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default=".", help="被治理项目根目录")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--approved-by", default="")
    sub = ap.add_subparsers(dest="command", required=True)
    def common(p):
        p.add_argument("--target", default=argparse.SUPPRESS, help="被治理项目根目录")
        p.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
        p.add_argument("--apply", action="store_true", default=argparse.SUPPRESS)
        p.add_argument("--approved-by", default=argparse.SUPPRESS)
        return p
    for name in ("check", "nodes", "sync-tests"):
        common(sub.add_parser(name, help=name))
    a = common(sub.add_parser("add", help="新增 TODO / issue"))
    a.add_argument("--kind", choices=sorted(KINDS), required=True)
    a.add_argument("--scope", required=True)
    a.add_argument("--title", required=True)
    a.add_argument("--detail", default="")
    a.add_argument("--severity", choices=sorted(SEVERITIES), default="med")
    a.add_argument("--owner", default="")
    a.add_argument("--refs", default="", help="逗号分隔：D-001 / capability:CODE / path:xxx")
    c = common(sub.add_parser("close", help="关闭工作项"))
    c.add_argument("--id", required=True)
    args = ap.parse_args(argv)
    target = Path(args.target).expanduser().resolve()
    try:
        if args.command == "check":
            result, rc = check(target), None
            rc = 0 if result["ok"] else 1
        elif args.command == "nodes":
            result = nodes(load_ledger(target / "governance"))
            rc = 0
        elif args.command == "sync-tests":
            result = sync_tests(target, approved_by=args.approved_by, apply=args.apply)
            rc = 0
        elif args.command == "add":
            refs = [x.strip() for x in args.refs.split(",") if x.strip()]
            result = add_item(target, kind=args.kind, scope=args.scope, title=args.title,
                              detail=args.detail, severity=args.severity,
                              owner=args.owner, refs=refs,
                              approved_by=args.approved_by, apply=args.apply)
            rc = 0
        else:
            result = close_item(target, item_id=args.id,
                                approved_by=args.approved_by, apply=args.apply)
            rc = 0
    except ValueError as exc:
        print(f"拒绝：{exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
          if args.json else result.get("message", json.dumps(result, ensure_ascii=False)))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
