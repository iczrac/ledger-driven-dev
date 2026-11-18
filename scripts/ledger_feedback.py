#!/usr/bin/env python3
"""反向回流通道：把真实项目的摩擦导出成匿名观察，并强制收敛成四产物之一。

为什么存在
----------
升级链是单向的（方法论仓库 -> M1-M8 -> 目标项目）。真实试用踩到的坑如果只落在
目标项目的 work_items 里，下一个项目会重踩。本脚本提供反向的管子：

    export（只读基线） -> triage（四产物） -> check（闭环校验） -> 下一个版本

设计约束
--------
* export 绝不写目标项目；写观察包需 --apply --approved-by <人>。
* 脱敏是数据驱动的：项目标识从目标项目自己的 registry / 账本提取，代码里不硬编码
  任何具体项目名词；额外词表可用 --terms 注入（文件不进仓库）。
* 观察 id 由内容派生，重复 export 幂等；不含时间戳，便于 diff 与回放。
* 每条已关闭观察必须指向一个真实存在的产物文件（校验器会检查）。

用法
----
    python3 scripts/ledger_feedback.py export --target P --json
    python3 scripts/ledger_feedback.py export --target P --out feedback/observations.jsonl \
        --apply --approved-by 张三
    python3 scripts/ledger_feedback.py triage --file feedback/observations.jsonl \
        --obs-id OBS-xxxxxxxxxxxx --disposition regression \
        --artifact-ref scripts/work_panel.py --reason '说明' --apply --approved-by 张三
    python3 scripts/ledger_feedback.py check --file feedback/observations.jsonl --json

退出码：0 成功；1 校验失败 / 被拒绝；2 输入错误。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

SCHEMA = "ledger-observations/1"
ROOT = Path(__file__).resolve().parents[1]

# 四产物 + 明确不修。wontfix 也必须有理由，但不需要产物引用。
DISPOSITIONS = ("invariant", "scenario", "migration", "regression", "wontfix")
NEEDS_ARTIFACT = ("invariant", "scenario", "migration", "regression")
REQUIRED = ("schema", "obs_id", "source_ref", "method_version", "phase", "symptom",
            "affected_axis", "severity", "evidence_sha", "status")
AXES = ("method_version", "ledger_version", "tool_hashes", "method_assets",
        "board_skeleton", "installed_assets", "work_items", "test_results",
        "access", "lifecycle", "registry", "evidence", "hygiene", "scale", "general")

# 症状关键词 -> 受影响轴。只是默认分类，triage 时可人工改。
AXIS_HINTS = (
    ("registry", "registry"), ("多项目", "registry"), ("monorepo", "registry"),
    ("test_report", "test_results"), ("实测报告", "test_results"),
    ("declared", "evidence"), ("verified", "evidence"), ("证据", "evidence"),
    ("work_items", "work_items"), ("工作台", "work_items"),
    ("lifecycle", "lifecycle"), ("冻结", "lifecycle"),
    ("access", "access"), ("agent", "access"), ("网关", "access"),
    ("asset", "installed_assets"), ("副本", "installed_assets"), ("skill", "installed_assets"),
    ("board", "board_skeleton"), ("看板", "board_skeleton"), ("embed", "board_skeleton"),
    ("hygiene", "hygiene"), ("脱敏", "hygiene"), ("分片", "scale"), ("规模", "scale"),
    ("upgrade", "method_version"), ("升级", "method_version"), ("迁移", "method_version"),
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def classify(text: str) -> str:
    low = (text or "").lower()
    for needle, axis in AXIS_HINTS:
        if needle.lower() in low:
            return axis
    return "general"


def load_terms(path: str | None) -> list[tuple[str, str]]:
    """额外脱敏词表：每行 `词=>替换` 或纯词（替换为 <term>）。文件不进仓库。"""
    if not path:
        return []
    p = Path(path).expanduser()
    if not p.is_file():
        raise ValueError(f"词表不存在：{path}")
    out: list[tuple[str, str]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=>" in line:
            word, repl = (x.strip() for x in line.split("=>", 1))
        else:
            word, repl = line, "<term>"
        if word:
            out.append((word, repl))
    return out


def project_codes(ledger: dict, registry: dict) -> list[str]:
    """项目标识完全来自目标项目自身，代码里不内置任何具体项目名。"""
    codes: list[str] = []
    proj = registry.get("project", {}) if isinstance(registry, dict) else {}
    for key in ("code", "name", "prefix"):
        v = proj.get(key)
        if isinstance(v, str) and 0 < len(v) <= 40:
            codes.append(v)
    for item in (ledger.get("capability_model", {}).get("projects", []) or []):
        if not isinstance(item, dict):
            continue
        for key in ("code", "id", "name", "prefix"):
            v = item.get(key)
            if isinstance(v, str) and 0 < len(v) <= 40:
                codes.append(v)
    for w in (ledger.get("work_items", []) or []):
        scope = w.get("scope", "") if isinstance(w, dict) else ""
        if isinstance(scope, str) and "." in scope:
            codes.append(scope.split(".")[0])
    return sorted({c for c in codes if c}, key=len, reverse=True)


def redact(text: object, codes: list[str], extra: list[tuple[str, str]]) -> str:
    s = str(text if text is not None else "")
    # 负向后视排除路径中的目录名，避免把 examples/demo-shop 改成 examples/PROJ-shop
    for code in codes:
        s = re.sub(r"(?<![/\w])" + re.escape(code) + r"(?!\w)", "PROJ", s, flags=re.I)
    for word, repl in extra:
        s = re.sub(r"(?<![/\w])" + re.escape(word) + r"(?!\w)", repl, s, flags=re.I)
    s = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+", "<email>", s)
    s = re.sub(r"(?:gh[pousr]_|sk-|AKIA|xox[baprs]-)[A-Za-z0-9_-]{8,}", "<secret>", s)
    s = re.sub(r"/(?:Users|home|private|var|tmp)/[^\s\"'),;，、\]]+", "<abs>", s)
    s = re.sub(r"~/[^\s\"'),;，、\]]+", "<home>", s)
    return re.sub(r"\s+", " ", s).strip()


def make_obs(source_ref: str, method_version: str, phase: str, symptom: str,
             evidence: bytes, severity: str = "med", repro: str = "",
             expected: str = "", proposed: str = "", axis: str | None = None) -> dict:
    axis = axis or classify(symptom)
    if axis not in AXES:
        axis = "general"
    oid = "OBS-" + sha256_bytes("|".join((source_ref, phase, symptom, axis)).encode())[:12]
    return {
        "schema": SCHEMA,
        "obs_id": oid,
        "source_ref": source_ref,
        "method_version": method_version,
        "phase": phase,
        "symptom": symptom,
        "repro": repro,
        "expected": expected,
        "affected_axis": axis,
        "severity": severity,
        "evidence_sha": sha256_bytes(evidence)[:16],
        "proposed_change": proposed,
        "status": "open",
        "disposition": None,
        "artifact_ref": None,
        "reason": None,
    }


def current_method_version() -> str:
    """从权威源读取当前方法版本（只读文本，避免脚本间 import 耦合）。"""
    try:
        m = re.search(r'^METHOD_VERSION\s*=\s*"([^"]+)"',
                      (ROOT / "scripts" / "upgrade.py").read_text(encoding="utf-8"),
                      re.M)
        return m.group(1) if m else "unknown"
    except OSError:
        return "unknown"


def probe_verifier(target: Path, gov: Path) -> dict | None:
    """只读探测目标项目自己的校验器输出；失败/超时不影响导出。"""
    v = gov / "verify_ledger.py"
    if not v.is_file():
        return None
    cmd = [sys.executable, str(v), "--root", str(target),
           "--registry", str(gov / "registry.json"),
           "--ledger", str(gov / "DECISION_LEDGER.json"),
           "--board", str(gov / "index.html"), "--json"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=25, cwd=str(target))
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode not in (0, 1):
        return None
    try:
        return json.loads(r.stdout)
    except (ValueError, TypeError):
        return None


def collect(target: Path, notes: list[str], with_probe: bool,
            extra: list[tuple[str, str]], phase: str) -> dict:
    """只读采集。返回观察列表与匿名项目标识。"""
    target = Path(target).expanduser().resolve()
    gov = target / "governance"
    ledger_path = gov / "DECISION_LEDGER.json"
    registry_path = gov / "registry.json"
    if not ledger_path.is_file() or not registry_path.is_file():
        raise ValueError("目标项目缺少 governance/DECISION_LEDGER.json 或 registry.json")
    ledger_bytes = ledger_path.read_bytes()
    registry_bytes = registry_path.read_bytes()
    ledger = json.loads(ledger_bytes)
    registry = json.loads(registry_bytes)
    codes = project_codes(ledger, registry)
    source_ref = "project:" + sha256_bytes(registry_bytes)[:12]
    method_version = str((ledger.get("governance_meta") or {}).get("method_version")
                         or ledger.get("ledger_version") or "unknown")

    def r(text: object) -> str:
        return redact(text, codes, extra)

    obs: list[dict] = []

    # 1) 工作台上的 TODO / issue：真实试用摩擦的第一手记录
    for w in (ledger.get("work_items", []) or []):
        if not isinstance(w, dict) or w.get("status") == "closed":
            continue
        raw = json.dumps(w, ensure_ascii=False, sort_keys=True).encode()
        symptom = r(f"{w.get('title', '')}：{w.get('detail', '')}").strip("： ")
        obs.append(make_obs(
            source_ref, method_version, "runtime", symptom or r(w.get("id")), raw,
            severity={"high": "high", "low": "low"}.get(w.get("severity"), "med"),
            repro=r(f"work_items[{w.get('id')}] 仍为 {w.get('status')}"),
            expected="同类摩擦在方法论仓库有对应不变量 / 场景 / 迁移 / 回归测试",
            proposed="triage 成四产物之一，否则显式 wontfix 并写理由"))

    # 2) 未确认的经验候选：机器识别到信号但人没下结论
    for c in ((ledger.get("lessons") or {}).get("candidates", []) or []):
        if not isinstance(c, dict) or c.get("status") != "open":
            continue
        raw = json.dumps(c, ensure_ascii=False, sort_keys=True).encode()
        obs.append(make_obs(
            source_ref, method_version, "runtime",
            r(f"未确认经验候选 {c.get('kind')}：{c.get('reason')}"), raw,
            severity="low", axis="general",
            repro=r(f"lessons.candidates[{c.get('id')}] status=open"),
            expected="候选被确认成 items 并携带 insight / action"))

    # 3) 结构缺口：字段未启用本身是观察，不能因为校验器放行就消失
    gaps = (
        ("test_results", "节点测试结果投影未绑定：能力等级只能停留在 declared"),
        ("lifecycle", "生命周期状态未登记，缺失即放行"),
        ("governance_meta.activation", "激活状态占位缺失，绿灯语义无法区分未启用"),
    )
    for key, text in gaps:
        if key == "governance_meta.activation":
            present = "activation" in (ledger.get("governance_meta") or {})
        else:
            present = key in ledger
        if not present:
            obs.append(make_obs(
                source_ref, method_version, "verify", r(text), ledger_bytes,
                severity="med", repro=f"账本缺少 {key}",
                expected="未启用在三态校验中记为 na，且看板明示",
                proposed="补不变量 activation_state_valid 或显式 unbound 占位"))
    agents = (ledger.get("access") or {}).get("agents", [])
    if not agents:
        obs.append(make_obs(
            source_ref, method_version, "verify",
            "接入名册为空：默认拒绝生效但没有可用的激活路径", ledger_bytes,
            severity="med", axis="access",
            repro="access.agents 长度为 0",
            expected="至少存在 owner 与 observer 两类已批准 Agent",
            proposed="迁移补最小名册并把 register 纳入升级后流程"))

    # 4) 升级记录：把每次迁移作为基线事件，供升级前后对比
    for ev in ((ledger.get("governance_meta") or {}).get("upgrade_log", []) or []):
        if not isinstance(ev, dict):
            continue
        raw = json.dumps(ev, ensure_ascii=False, sort_keys=True).encode()
        obs.append(make_obs(
            source_ref, method_version, "upgrade",
            r(f"迁移 {ev.get('from')} -> {ev.get('to')} 执行了 "
              f"{len(ev.get('migrations', []) or [])} 条：{', '.join(ev.get('migrations', []) or [])}"),
            raw, severity="low", axis="method_version",
            repro="governance_meta.upgrade_log 中的 apply 事件",
            expected="升级前后各导出一次观察包，可 diff 出新增/消失的摩擦"))

    # 5) 版本落差与校验器代际：这两项不会被「全绿」掩盖
    latest = current_method_version()
    if latest != "unknown" and method_version != latest:
        obs.append(make_obs(
            source_ref, method_version, "upgrade",
            f"目标项目方法版本 {method_version} 落后于权威源 {latest}："
            "已发布的修复尚未被真实项目消费", ledger_bytes,
            severity="high", axis="method_version",
            repro="对比 governance_meta.method_version 与升级脚本 METHOD_VERSION",
            expected="升级前后各导出一次观察包，可 diff 出消失的摩擦",
            proposed="先导出基线，再执行带人批准的升级，最后复导对比"))
    if with_probe:
        out = probe_verifier(target, gov)
        if isinstance(out, dict):
            if "na" not in out:
                obs.append(make_obs(
                    source_ref, method_version, "verify",
                    "目标项目校验器仍是两态语义：输出没有 na 字段，"
                    "未启用项会被记成通过", ledger_bytes,
                    severity="high", axis="method_version",
                    repro="目标项目 governance/verify_ledger.py --json",
                    expected="三态输出含 na / all_active / activation.inactive",
                    proposed="同步三态校验器副本并重跑 --strict"))
            for c in (out.get("checks", []) or []):
                if not isinstance(c, dict):
                    continue
                status = c.get("status")
                if status is None:
                    status = "fail" if c.get("ok") is False else "pass"
                if status not in ("fail", "na", "warn"):
                    continue
                raw = json.dumps(c, ensure_ascii=False, sort_keys=True).encode()
                obs.append(make_obs(
                    source_ref, method_version, "verify",
                    r(f"校验项 {c.get('id')} 状态 {status}：{c.get('detail')}"), raw,
                    severity="high" if status == "fail" else "med",
                    axis="general",
                    repro="目标项目 governance/verify_ledger.py --json",
                    expected="失败项被修复，na 项在摘要中明示未启用"))

    # 6) 人工补充的观察（可能来自评审、CI 日志、升级现场）
    for i, note in enumerate(notes):
        obs.append(make_obs(
            source_ref, method_version, phase or "manual", r(note),
            f"note:{i}:{note}".encode(), severity="med",
            repro="人工记录（--note）", expected="四产物之一或 wontfix"))

    # 去重（同一症状多次出现只保留一条），按 obs_id 排序保证幂等
    uniq: dict[str, dict] = {}
    for o in obs:
        uniq.setdefault(o["obs_id"], o)
    return {"schema": SCHEMA, "source_ref": source_ref,
            "method_version": method_version, "observations": sorted(
                uniq.values(), key=lambda x: x["obs_id"])}


def read_lines(path: Path) -> list[dict]:
    p = Path(path).expanduser()
    if not p.is_file():
        raise ValueError(f"观察包不存在：{path}")
    rows = []
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except ValueError as e:
            raise ValueError(f"第 {i} 行不是合法 JSON：{e}") from e
    return rows


def write_lines(path: Path, rows: list[dict]) -> None:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n"
                         for x in rows), encoding="utf-8")


def check_rows(rows: list[dict], root: Path = ROOT) -> dict:
    errors: list[str] = []
    seen: set[str] = set()
    closed = 0
    axes: dict[str, int] = {}
    for i, o in enumerate(rows, 1):
        if not isinstance(o, dict):
            errors.append(f"第 {i} 行不是对象")
            continue
        missing = [k for k in REQUIRED if not o.get(k)]
        if missing:
            errors.append(f"{o.get('obs_id', i)} 缺字段 {','.join(missing)}")
        if o.get("schema") != SCHEMA:
            errors.append(f"{o.get('obs_id', i)} schema 非法")
        oid = o.get("obs_id", "")
        if oid in seen:
            errors.append(f"{oid} 重复")
        seen.add(oid)
        expected = "OBS-" + sha256_bytes("|".join((
            str(o.get("source_ref", "")), str(o.get("phase", "")),
            str(o.get("symptom", "")), str(o.get("affected_axis", "")))).encode())[:12]
        if oid != expected:
            errors.append(f"{oid} 内容指纹不匹配（疑似手改）")
        if o.get("affected_axis") not in AXES:
            errors.append(f"{oid} 受影响轴非法")
        if o.get("status") not in ("open", "closed"):
            errors.append(f"{oid} status 非法")
        axes[o.get("affected_axis", "?")] = axes.get(o.get("affected_axis", "?"), 0) + 1
        if o.get("status") != "closed":
            continue
        closed += 1
        disp = o.get("disposition")
        if disp not in DISPOSITIONS:
            errors.append(f"{oid} 关闭但 disposition 非法")
        if disp in NEEDS_ARTIFACT and not o.get("artifact_ref"):
            errors.append(f"{oid} 是 {disp} 但缺 artifact_ref")
        ref = o.get("artifact_ref") or ""
        if ref:
            file_part = ref.split("::")[0].split("#")[0]
            if file_part and not (root / file_part).exists():
                errors.append(f"{oid} 产物引用不存在：{file_part}")
        if not o.get("reason"):
            errors.append(f"{oid} 关闭但缺 reason")
    feedback_closed = sum(1 for o in rows if isinstance(o, dict)
                          and o.get("status") == "closed"
                          and o.get("disposition") in NEEDS_ARTIFACT)
    return {"ok": not errors, "total": len(rows), "open": len(rows) - closed,
            "closed": closed, "feedback_closed": feedback_closed,
            "axes": axes, "errors": errors}


def cmd_export(args) -> dict:
    extra = load_terms(args.terms)
    data = collect(args.target, args.note, not args.no_probe, extra, args.phase)
    rows = data["observations"]
    payload = {"schema": SCHEMA, "source_ref": data["source_ref"],
               "method_version": data["method_version"], "count": len(rows),
               "sha256": sha256_bytes("".join(
                   json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n"
                   for x in rows).encode()),
               "observations": rows}
    if args.out:
        if not (args.apply and args.approved_by):
            return {"mode": "dry-run", **payload,
                    "reason": "写盘需要 --apply --approved-by <人>"}
        write_lines(args.out, rows)
        return {"mode": "apply", "out": str(Path(args.out).expanduser().resolve()),
                "approved_by": args.approved_by, **payload}
    return {"mode": "dry-run", **payload}


def cmd_triage(args) -> dict:
    rows = read_lines(args.file)
    hit = [o for o in rows if o.get("obs_id") == args.obs_id]
    if len(hit) != 1:
        raise ValueError(f"观察 id 未唯一命中：{args.obs_id}")
    if args.disposition not in DISPOSITIONS:
        raise ValueError("disposition 必须是四产物之一或 wontfix")
    if args.disposition in NEEDS_ARTIFACT and not args.artifact_ref:
        raise ValueError("四产物类关闭必须给 artifact_ref")
    if not args.reason:
        raise ValueError("关闭观察必须写 reason")
    if not (args.apply and args.approved_by):
        return {"mode": "dry-run", "obs_id": args.obs_id,
                "disposition": args.disposition,
                "reason": "写盘需要 --apply --approved-by <人>"}
    o = hit[0]
    o.update({"status": "closed", "disposition": args.disposition,
              "artifact_ref": args.artifact_ref or None, "reason": args.reason,
              "approved_by": args.approved_by})
    write_lines(args.file, rows)
    return {"mode": "apply", "obs_id": args.obs_id,
            "disposition": args.disposition, "check": check_rows(rows)}


def cmd_check(args) -> dict:
    return {"mode": "check", **check_rows(read_lines(args.file))}


def cmd_report(args) -> dict:
    result = check_rows(read_lines(args.file))
    rows = read_lines(args.file)
    phases: dict[str, int] = {}
    dispositions: dict[str, int] = {}
    for o in rows:
        phases[o.get("phase", "?")] = phases.get(o.get("phase", "?"), 0) + 1
        d = o.get("disposition") or "untriaged"
        dispositions[d] = dispositions.get(d, 0) + 1
    return {"mode": "report", "total": result["total"], "open": result["open"],
            "closed": result["closed"], "feedback_closed": result["feedback_closed"],
            "axes": result["axes"], "phases": phases, "dispositions": dispositions,
            "ok": result["ok"], "errors": result["errors"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="反向回流：观察导出 / triage / 闭环校验")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    sub = ap.add_subparsers(dest="command", required=True)

    e = sub.add_parser("export", help="只读采集目标项目摩擦")
    e.add_argument("--target", required=True)
    e.add_argument("--out", help="观察包输出路径（需 --apply --approved-by）")
    e.add_argument("--phase", default="manual", help="手工观察的阶段标签")
    e.add_argument("--note", action="append", default=[], help="人工补充观察，可重复")
    e.add_argument("--terms", help="额外脱敏词表（文件不进仓库）")
    e.add_argument("--no-probe", action="store_true", help="不运行目标项目校验器")
    e.add_argument("--apply", action="store_true")
    e.add_argument("--approved-by")

    t = sub.add_parser("triage", help="把观察收敛成四产物之一")
    t.add_argument("--file", required=True)
    t.add_argument("--obs-id", required=True)
    t.add_argument("--disposition", required=True, choices=DISPOSITIONS)
    t.add_argument("--artifact-ref", help="产物相对路径，可带 ::测试 id 或 #锚点")
    t.add_argument("--reason", required=True)
    t.add_argument("--apply", action="store_true")
    t.add_argument("--approved-by")

    c = sub.add_parser("check", help="闭环校验")
    c.add_argument("--file", required=True)

    r = sub.add_parser("report", help="按轴 / 阶段 / 处置聚合")
    r.add_argument("--file", required=True)

    # --json 允许出现在子命令前或后；SUPPRESS 避免子 parser 的默认值覆盖父级
    for p in (e, t, c, r):
        p.add_argument("--json", action="store_true", default=argparse.SUPPRESS)

    args = ap.parse_args(argv)
    as_json = getattr(args, "json", False)
    try:
        fn = {"export": cmd_export, "triage": cmd_triage,
              "check": cmd_check, "report": cmd_report}[args.command]
        result = fn(args)
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False) if as_json
              else f"输入错误：{exc}", file=sys.stderr)
        return 2
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if args.command == "export":
            print(f"[{result['mode']}] {result['source_ref']} @ {result['method_version']} "
                  f"共 {result['count']} 条观察，digest={result['sha256'][:16]}")
            for o in result["observations"]:
                print(f"  {o['obs_id']} [{o['affected_axis']}] {o['symptom'][:100]}")
            if result.get("out"):
                print(f"  已写入 {result['out']}")
            elif result.get("reason"):
                print(f"  {result['reason']}")
        elif args.command == "triage":
            print(f"[{result['mode']}] {result['obs_id']} -> {result['disposition']}")
            if "check" in result:
                print(f"  闭环：{result['check']['total']} 条 / "
                      f"feedback_closed={result['check']['feedback_closed']} / "
                      f"ok={result['check']['ok']}")
        else:
            print(f"total={result['total']} open={result['open']} "
                  f"closed={result['closed']} "
                  f"feedback_closed={result['feedback_closed']} ok={result['ok']}")
            for err in result.get("errors", []):
                print(f"  ERROR {err}")
    if args.command in ("check", "report") and not result.get("ok", True):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
