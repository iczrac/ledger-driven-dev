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
    python3 scripts/work_panel.py --target P import-report --from ci/junit.xml \
        --adapter auto --source-dir src,tests --apply --approved-by 张三 --json

v1.3.0 报告契约
----------------
`governance/test_report.json` 是**开放契约**：只要求 `schema` / `summary` /
`cases[]` / `overall` / `evidence_binding`，不要求由哪个测试框架产生。标准库栈
可直接用 `run_tests.py` 生成；其它栈用 `import-report` 把 JUnit XML、jest JSON
或任意符合契约的 JSON 规范化成同一份报告，再照常 `sync-tests` → 生成器取证。
`source_adapter` 只留在原始报告里，账本投影仍只保留看板需要的字段。

退出码：0 成功；1 被拒绝 / 校验失败；2 输入错误。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parents[1]
# 投影宣告与升级器 / 校验器 / 生成器共用唯一判据。
sys.path.insert(0, str(ROOT / "templates"))

from ledger_io import load_ledger, write_ledger  # noqa: E402
from registry_codec import projection_opted_out  # noqa: E402
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
REPORT_SCHEMA = "ledger-test-report/1"
ADAPTERS = {"auto", "ledger", "junit", "jest"}
SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx",
                   ".go", ".java", ".rs", ".rb", ".php"}


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


CLOSE_KINDS = ("manual", "capability_verified", "file_exists")


def close_condition_met(cond: dict, caps: dict[str, dict],
                        repo_root: Path | None) -> tuple[bool, str]:
    """工作项关闭条件是否已被证据满足 → (满足?, 说明)。

    结构自洽不等于业务真实：事情做完了、工作项还挂 open，看板与 next_queue
    会指挥下一个执行者重做。让每条工作项声明机器可判定的关闭条件，
    条件一旦被证据满足就禁止继续 open。无法判定的条件视为未满足（宁可漏关）。
    """
    if not isinstance(cond, dict):
        return False, "close_condition 必须是对象"
    kind = cond.get("kind")
    if kind == "manual":
        return False, "人工判定"
    if kind == "capability_verified":
        code = str(cond.get("capability", "")).strip()
        info = caps.get(code)
        if info is None:
            return False, f"能力不存在 {code}"
        return info.get("tier") == "verified", f"{code} tier={info.get('tier')}"
    if kind == "file_exists":
        rel = str(cond.get("path", "")).strip().strip("/")
        if repo_root is None:
            return False, "缺少项目根，无法判定"
        exists = bool(rel) and (Path(repo_root) / rel).exists()
        return exists, f"{rel} 存在={exists}"
    return False, f"未知 close_condition.kind={kind}"


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
    cap_idx = cap_index(ledger)
    caps = set(cap_idx)
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
        cond = x.get("close_condition")
        if cond is not None:
            if not isinstance(cond, dict) or cond.get("kind") not in CLOSE_KINDS:
                errs.append(f"{wid}: close_condition.kind 必须是 {'/'.join(CLOSE_KINDS)}")
            elif x.get("status") in ("open", "doing"):
                met, why = close_condition_met(
                    cond, cap_idx, Path(governance_dir).parent if governance_dir else None)
                if met:
                    errs.append(f"{wid}: 关闭条件已满足（{why}）但仍 {x.get('status')}"
                                "——事件已完成，账本不许继续挂账")
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


def detect_adapter(raw: bytes) -> str:
    head = raw.lstrip()[:256]
    if head.startswith(b"<"):
        return "junit"
    try:
        d = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("无法识别报告格式，请显式指定 --adapter")
    if isinstance(d, dict) and d.get("schema") == REPORT_SCHEMA:
        return "ledger"
    if isinstance(d, dict) and "testResults" in d:
        return "jest"
    raise ValueError("无法识别报告格式，请显式指定 --adapter")


def _binding_from_dirs(root: Path, dirs: list[str]) -> dict:
    """与 run_tests.py 同口径的源码绑定；路径一律相对项目根，避免绝对路径污染。"""
    root = root.resolve()
    inputs: list[dict] = []
    for rel in dirs:
        base = root / rel
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
                continue
            try:
                name = path.resolve().relative_to(root).as_posix()
            except ValueError:
                continue
            inputs.append({"path": name,
                           "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return {
        "algorithm": "sha256-files-v1",
        "inputs": inputs,
        "source_digest": hashlib.sha256(
            "".join(f"{i['path']}:{i['sha256']}\n" for i in inputs).encode("utf-8")
        ).hexdigest()[:16],
        "source_adapter": "import-report",
    }


def _cases_from_ledger(d: dict) -> list[dict]:
    return [{"id": c.get("id", ""), "file": c.get("file", ""),
             "status": c.get("status", ""), "seconds": c.get("seconds", 0)}
            for c in d.get("cases", []) if isinstance(c, dict)]


def default_source_dirs(target: Path) -> list[str]:
    """探测项目的源码/测试布局，返回用于证据绑定的目录列表。

    单一布局（根目录 src/ + tests/）优先；monorepo 则扫描 projects/* 下的
    src 与 tests 子目录。返回相对项目根的路径，绝不返回绝对路径。
    v1.8.0：修复默认 src,tests 对 monorepo 产生空绑定的缺口。
    """
    root = Path(target).expanduser().resolve()
    found: list[str] = []
    for rel in ("src", "tests"):
        if (root / rel).is_dir():
            found.append(rel)
    if found:
        return found
    projects = root / "projects"
    if projects.is_dir():
        for child in sorted(projects.iterdir()):
            if not child.is_dir():
                continue
            for sub in ("src", "tests"):
                d = child / sub
                if d.is_dir():
                    found.append(d.relative_to(root).as_posix())
    return found


def _unit_test_whitelist(target: Path) -> dict[str, str]:
    """从账本 capability_model 收集 unit_tests 白名单：文件名 → 相对路径。

    仅用于把 JUnit classname 反解成真实测试文件路径；白名单来自单一事实源，
    不凭空猜路径。缺账本时返回空映射（此时 classname_to_file 不编造）。
    """
    try:
        ledger = load_ledger(Path(target) / "governance")
    except (ValueError, OSError):
        return {}  # 无账本时不猜路径；空绑定拒绝仍会在本报告里生效
    model = ledger.get("capability_model") or {}
    out: dict[str, str] = {}
    for proj in model.get("projects") or []:
        for mod in proj.get("modules") or []:
            for cap in mod.get("caps") or []:
                for item in cap.get("evidence", {}).get("unit_test") or []:
                    rel = str(item)
                    out[Path(rel).name] = rel
                for rel in cap.get("unit_tests") or []:
                    rel = str(rel)
                    out[Path(rel).name] = rel
    return out


def classname_to_file(classname: str, whitelist: dict[str, str]) -> str:
    """把 JUnit classname（如 a.b.test_x）反解为账本白名单内的真实路径。

    只接受 basename 精确命中白名单；命中不到返回空串，绝不猜测。
    """
    if not classname or not whitelist:
        return ""
    # classname 可能带类名/测试名后缀（a.b.test_x.Test.test_y），
    # 逐段尝试，取第一个命中白名单的文件名；不命中返回空串（不猜）。
    parts = classname.split(".")
    for i in range(len(parts), 0, -1):
        leaf = parts[i - 1]
        candidate = leaf if leaf.endswith(".py") else leaf + ".py"
        if candidate in whitelist:
            return whitelist[candidate]
    return ""


def _cases_from_junit(raw: bytes, whitelist: dict[str, str] | None = None) -> list[dict]:
    try:
        tree = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError(f"JUnit XML 解析失败：{exc}")
    whitelist = whitelist or {}
    cases = []
    for tc in tree.iter("testcase"):
        name = tc.get("name") or "unnamed"
        cls = tc.get("classname") or ""
        kids = {child.tag.split("}")[-1] for child in tc}
        status = ("skip" if "skipped" in kids else
                  "error" if "error" in kids else
                  "fail" if "failure" in kids else "pass")
        try:
            seconds = round(float(tc.get("time") or 0), 6)
        except ValueError:
            seconds = 0
        # v1.8.0：JUnit 原生无 file 属性，用 classname 按账本单位测试白名单反解。
        file_path = tc.get("file") or classname_to_file(cls, whitelist)
        cases.append({"id": f"{cls}.{name}" if cls else name,
                      "file": file_path, "status": status,
                      "seconds": seconds})
    return cases


def _cases_from_jest(d: dict) -> list[dict]:
    status_map = {"passed": "pass", "failed": "fail", "skipped": "skip",
                  "pending": "skip", "todo": "skip"}
    cases = []
    for tr in d.get("testResults", []) or []:
        if not isinstance(tr, dict):
            continue
        for a in tr.get("assertionResults", []) or []:
            if not isinstance(a, dict):
                continue
            cases.append({
                "id": a.get("fullName") or a.get("title") or "",
                "file": tr.get("name", ""),
                "status": status_map.get(a.get("status", ""), "error"),
                "seconds": round((a.get("duration") or 0) / 1000, 6),
            })
    return cases


def normalize_report(raw: bytes, adapter: str, target: Path,
                     dirs: list[str]) -> dict:
    """把任意受支持框架的报告规范化成 ledger-test-report/1，绝不伪造通过。"""
    kind = detect_adapter(raw) if adapter == "auto" else adapter
    if kind == "junit":
        cases = _cases_from_junit(raw, _unit_test_whitelist(target))
    else:
        try:
            d = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"报告不是合法 JSON：{exc}")
        if not isinstance(d, dict):
            raise ValueError("报告顶层必须是对象")
        cases = _cases_from_jest(d) if kind == "jest" else _cases_from_ledger(d)
    counts = {s: 0 for s in ("pass", "fail", "error", "skip")}
    for c in cases:
        if c["status"] in counts:
            counts[c["status"]] += 1
    load_errors = [] if cases else ["导入后用例为空：拒绝生成全绿报告"]
    binding = _binding_from_dirs(target, dirs)
    # v1.8.0 缺口 A：空证据绑定（sha256 空串）不得判绿，杜绝「形式合规实质无绑定」。
    if not binding["inputs"]:
        load_errors.append("证据绑定为空（源码目录不存在）：拒绝生成全绿报告")
    overall = "pass" if (cases and not counts["fail"] and not counts["error"]
                         and counts["pass"] > 0 and not load_errors) else "fail"
    return {
        "schema": REPORT_SCHEMA,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M HKT"),
        "test_dir": ",".join(dirs),
        "command": f"work_panel.py import-report --adapter {kind}",
        "load_errors": load_errors,
        "summary": {"total": len(cases), "passed": counts["pass"],
                    "failed": counts["fail"], "errors": counts["error"],
                    "skipped": counts["skip"]},
        "cases": cases,
        "overall": overall,
        "source_adapter": kind,
        "evidence_binding": binding,
    }


def import_report(target: Path, *, source: str, adapter: str = "auto",
                  dirs: list[str] | None = None,
                  approved_by: str = "", apply: bool = False) -> dict:
    """导入外部 CI 报告；默认 dry-run，写盘需 --apply --approved-by。"""
    target = Path(target).expanduser().resolve()
    src = Path(source).expanduser()
    if not src.is_file():
        raise ValueError(f"找不到外部报告：{src}")
    if adapter not in ADAPTERS:
        raise ValueError(f"适配器必须是 {sorted(ADAPTERS)}")
    scan_dirs = dirs or default_source_dirs(target)
    report = normalize_report(src.read_bytes(), adapter, target, scan_dirs)
    out = target / REPORT_REL
    base = {"schema": SCHEMA_ACTION, "action": "import-report",
            "adapter": report["source_adapter"], "cases": len(report["cases"]),
            "overall": report["overall"],
            "source_digest": report["evidence_binding"]["source_digest"],
            "out": REPORT_REL}
    if not apply:
        return {**base, "mode": "dry-run",
                "message": "只读预演；写盘需 --apply --approved-by <人>"}
    if not approved_by:
        raise ValueError("导入测试报告必须提供 --approved-by（人工批准）")
    overwrote = out.is_file()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    return {**base, "mode": "apply", "noop": False, "overwrote": overwrote,
            "approved_by": approved_by,
            "message": "报告已规范化；接着跑 sync-tests 与生成器取证"}


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


def activation_from_report(tr: dict) -> dict:
    """v2.0.0：据真实报告同步证据激活态，杜绝账本占位与实际相反。

    无报告 / 报告未通过 / 无用例时保持 unbound（诚实），不伪造 active。
    报告 overall=pass 且有用例时置 active，reason 说明绑定来源。
    """
    cases = tr.get("cases") or []
    bound = bool(cases) and tr.get("overall") == "pass"
    return {
        "schema": "evidence-activation/1",
        "state": "active" if bound else "unbound",
        "reason": (f"已绑定 {REPORT_REL}（{len(cases)} 用例，overall=pass），证据能力激活"
                   if bound else "测试报告未通过或无用例，证据能力未激活"),
        "all_active": bound,
    }


def sync_tests(target: Path, *, approved_by: str = "", apply: bool = False) -> dict:
    target = Path(target)
    gov = target / "governance"
    ledger = load_ledger(gov)
    if projection_opted_out(ledger):
        # 宣告 opt-out 就没有写入动作，因此不要求 --approved-by（无写无需批准）。
        return {"schema": SCHEMA_ACTION, "action": "sync-tests",
                "mode": "apply" if apply else "dry-run",
                "noop": True, "policy": "opt-out", "cases": 0,
                "message": "账本宣告 test_results opt-out；不写投影，无需批准"}
    tr = test_results_from_report(gov)
    if tr is None:
        raise ValueError(f"找不到可读的测试报告：{REPORT_REL}")
    current = ledger.get("test_results")
    activation = activation_from_report(tr)
    meta = ledger.get("governance_meta") or {}
    activation_changed = meta.get("activation") != activation
    same = current == tr and not activation_changed
    if not apply:
        return {"schema": SCHEMA_ACTION, "action": "sync-tests", "mode": "dry-run",
                "noop": same, "cases": len(tr["cases"]),
                "source_sha256": tr["source_sha256"],
                "activation": activation["state"],
                "message": "只读预演；写盘需 --apply --approved-by <人>"}
    if not approved_by:
        raise ValueError("同步测试结果必须提供 --approved-by（人工批准）")
    if same:
        return {"schema": SCHEMA_ACTION, "action": "sync-tests", "mode": "apply",
                "noop": True, "cases": len(tr["cases"]),
                "message": "投影已与当前报告一致，无需写入"}
    ledger["test_results"] = tr
    if isinstance(ledger.get("governance_meta"), dict):
        ledger["governance_meta"]["activation"] = activation
    write_ledger(gov, ledger)
    return {"schema": SCHEMA_ACTION, "action": "sync-tests", "mode": "apply",
            "noop": False, "approved_by": approved_by, "cases": len(tr["cases"]),
            "source_sha256": tr["source_sha256"], "activation": activation["state"],
            "message": "测试结果投影与激活态已写回账本并同步看板"}


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
               resolution: str = "", close_condition: dict | None = None,
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
    if close_condition is not None:
        if close_condition.get("kind") not in CLOSE_KINDS:
            raise ValueError(f"close_condition.kind 必须是 {'/'.join(CLOSE_KINDS)}")
        item["close_condition"] = close_condition
    # 声明了机器可判定关闭条件的工作项，关闭时必须写清依据，杜绝「无理由关闭」。
    if item.get("close_condition") and not resolution.strip():
        raise ValueError("该工作项声明了 close_condition，关闭必须提供 --resolution 说明证据")
    item["status"] = "done"
    item["closed_by"] = approved_by
    item["closed_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    if resolution.strip():
        item["resolution"] = resolution.strip()
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
    c.add_argument("--resolution", default="", help="关闭依据（声明了 close_condition 时必填）")
    c.add_argument("--close-condition", dest="close_condition", default="",
                   help='机器可判定关闭条件 JSON，如 {"kind":"file_exists","path":"a/b.json"}')
    ir = common(sub.add_parser("import-report", help="导入外部 CI 测试报告"))
    ir.add_argument("--from", dest="source", required=True, help="外部报告路径")
    ir.add_argument("--adapter", choices=sorted(ADAPTERS), default="auto")
    ir.add_argument("--source-dir", dest="source_dirs", default=None,
                    help="逗号分隔；缺省时自动探测 src/tests 或 projects/*/{src,tests}")
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
        elif args.command == "import-report":
            dirs = ([x.strip() for x in args.source_dirs.split(",") if x.strip()]
                    if args.source_dirs else None)
            result = import_report(target, source=args.source, adapter=args.adapter,
                                   dirs=dirs, approved_by=args.approved_by,
                                   apply=args.apply)
            rc = 0
        elif args.command == "add":
            refs = [x.strip() for x in args.refs.split(",") if x.strip()]
            result = add_item(target, kind=args.kind, scope=args.scope, title=args.title,
                              detail=args.detail, severity=args.severity,
                              owner=args.owner, refs=refs,
                              approved_by=args.approved_by, apply=args.apply)
            rc = 0
        else:
            cond = json.loads(args.close_condition) if args.close_condition else None
            result = close_item(target, item_id=args.id, resolution=args.resolution,
                                close_condition=cond,
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
