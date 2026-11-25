#!/usr/bin/env python3
"""系统级看板生成器：模板 + 各项目账本 -> CapabilityForge/governance/index.html。

纪律
----
1. `templates/system_index.html.template` 是唯一权威骨架；项目里禁止手改 HTML。
2. 数据段 `const SYSTEM_DATA = {...}` 由各项目 governance/DECISION_LEDGER.json
   实时投影，系统看板不产生第二事实源；顶层 CapabilityForge 不是账本主体。
3. 兼容锚只读各项目 spec_check.json，版本比较直接复用 spec_check 的判据实现；
   趋势只读账本 history.events 的 state_digest，均不新增事实源。
4. `check` 全程只读：骨架摘要 != 模板摘要 => 手改骨架；数据 != 重算 => 手改数据。
5. 幂等：数据段不含生成时刻，as_of 取各账本 last_updated 的最大值；
   停滞时数相对该 as_of 计算，而非机器当前时间。

输出 schema: system-board-build/1 · system-board-check/1 · system-board-data/2。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve()
METHOD_ROOT = SCRIPT.parents[1]
DATA_RE = re.compile(r"const SYSTEM_DATA = .*?;\nlet DATA = SYSTEM_DATA;", re.S)
DATA_CAPTURE_RE = re.compile(r"const SYSTEM_DATA = (\{.*\});\nlet DATA = SYSTEM_DATA;", re.S)
PLACEHOLDER = "const SYSTEM_DATA = /*SYSTEM*/;\nlet DATA = SYSTEM_DATA;"
TEMPLATE_REL = "templates/system_index.html.template"
OUTPUT_REL = "governance/index.html"
BACKUP_DIR = ".system-board-backups"
SCHEMA_BUILD = "system-board-build/1"
SCHEMA_CHECK = "system-board-check/1"


def sha256_bytes(raw: bytes) -> str:
    import hashlib
    return hashlib.sha256(raw).hexdigest()


def skeleton_digest(html: str) -> str:
    if not DATA_RE.search(html):
        raise ValueError("找不到 const SYSTEM_DATA / let DATA 标记，无法计算骨架摘要")
    return sha256_bytes(DATA_RE.sub(lambda _m: PLACEHOLDER, html, count=1).encode("utf-8"))


def template_text(method_root: Path = METHOD_ROOT) -> str:
    p = Path(method_root) / TEMPLATE_REL
    if not p.is_file():
        raise ValueError(f"权威模板不存在：{p}")
    return p.read_text(encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parse_event_ts(raw: str) -> datetime | None:
    """账本历史时间戳（如 `2026-11-25 20:08 HKT`）-> UTC+8 时间；不可解析返回 None。"""
    if not raw:
        return None
    try:
        dt = datetime.strptime(raw.strip(), "%Y-%m-%d %H:%M HKT")
    except (TypeError, ValueError):
        return None
    return dt.replace(tzinfo=timezone(timedelta(hours=8)))


def history_projection(led: dict, as_of: datetime | None) -> dict:
    """从 history.events 的 state_digest 复算趋势；不产生新事件、不写账本。"""
    events = (led.get("history") or {}).get("events") or []
    series = []
    for ev in events:
        digest = ev.get("state_digest") or {}
        states = [v for v in digest.values() if isinstance(v, dict)]
        n = len(states)
        verified = sum(1 for v in states if v.get("t") == "verified")
        changes = ev.get("changes") or {}
        series.append({
            "seq": ev.get("seq"), "ts": ev.get("ts"), "type": ev.get("type"),
            "caps": n, "verified": verified,
            "verified_coverage": round(verified / n, 4) if n else 0,
            "avg_level": round(sum(float(v.get("l") or 0) for v in states) / n, 3) if n else 0,
            "avg_completion": round(sum(float(v.get("c") or 0) for v in states) / n, 3) if n else 0,
            "added": len(changes.get("added") or []),
            "level_transitions": len(changes.get("level_transitions") or []),
            "evidence_changes": len(changes.get("evidence_changes") or []),
        })
    last_ts = parse_event_ts(series[-1]["ts"]) if series else None
    stale_hours = (round((as_of - last_ts).total_seconds() / 3600, 1)
                   if as_of and last_ts else None)
    if not series:
        status = "no_events"
    elif stale_hours is None:
        status = "unknown"
    elif stale_hours <= 24:
        status = "fresh"
    elif stale_hours <= 72:
        status = "aging"
    else:
        status = "stale"
    return {"events": len(series), "series": series,
            "stale_hours": stale_hours, "stale_status": status,
            "last_event_ts": series[-1]["ts"] if series else None}


def _compat_detail(system_root: Path, child: Path, anchor: dict, ledgers: dict[str, dict]) -> dict:
    """单个组合锚的状态复算；口径与 spec_check.check_compat 完全一致。"""
    import spec_check as sc  # 同仓判据实现，避免第二套 semver / 版本源口径

    repo = anchor.get("repo", "")
    target = (child / repo).resolve()
    entry = {"consumer": child.name, "repo": repo,
             "min_version": anchor.get("min_version"),
             "note": anchor.get("note", "")}
    target_dir = next((p for p in ledgers if (system_root / p).resolve() == target), None)
    if target_dir:
        tled = ledgers[target_dir]
        entry["provider"] = tled.get("title") or target_dir
        entry["provider_dir"] = target_dir
        gmeta = tled.get("governance_meta") or {}
        entry["provider_version"] = gmeta.get("method_version") or tled.get("ledger_version") or "—"
    else:
        entry["provider"] = target.name
        entry["provider_dir"] = ""
        entry["provider_version"] = "—"
    if not target.is_dir():
        return {**entry, "found_version": None, "status": "repo_missing"}
    src = anchor.get("version_source") or {}
    if not src.get("file") or ("json_key" not in src and "regex" not in src):
        return {**entry, "found_version": None, "status": "bad_config"}
    try:
        found = sc._read_version_source(child, child / repo, src)
    except (OSError, KeyError, ValueError, re.error, IndexError) as exc:
        return {**entry, "found_version": None, "status": "version_unreadable",
                "error": str(exc)[:120]}
    if not found:
        return {**entry, "found_version": None, "status": "version_not_found"}
    try:
        ok = sc._semver_key(str(anchor["min_version"])) <= sc._semver_key(found)
    except (TypeError, KeyError, ValueError):
        return {**entry, "found_version": found, "status": "version_unparsable"}
    return {**entry, "found_version": found, "status": "ok" if ok else "below_anchor"}


def compat_projection(system_root: Path, ledgers: dict[str, dict]) -> dict:
    """扫描各仓 spec_check.json 的 compat.anchors，复算组合状态与升级影响面。"""
    root = Path(system_root)
    anchors: list[dict] = []
    for child in sorted(root.iterdir()):
        if child.name.startswith(".") or not child.is_dir():
            continue
        spec = child / "spec_check.json"
        if not spec.is_file():
            continue
        cfg = read_json(spec)
        for anchor in ((cfg.get("compat") or {}).get("anchors") or []):
            anchors.append(_compat_detail(root, child, anchor, ledgers))
    impacts: dict[str, list[str]] = {}
    for a in anchors:
        if a["provider_dir"]:
            impacts.setdefault(a["provider_dir"], []).append(a["consumer"])
    return {"anchors": anchors,
            "summary": {"total": len(anchors),
                        "ok": sum(1 for a in anchors if a["status"] == "ok"),
                        "blocked": sum(1 for a in anchors if a["status"] != "ok")},
            "impact": [{"provider": k, "consumers": sorted(set(v))}
                       for k, v in sorted(impacts.items())]}


def project_roles(system_root: Path) -> dict[str, str]:
    """README 在册项目表是展示用角色说明；缺表不阻断，按账本项目码投影。"""
    readme = Path(system_root) / "README.md"
    if not readme.is_file():
        return {}
    roles: dict[str, str] = {}
    for line in readme.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] and not set(cells[0]) <= set("-: "):
            roles[cells[0]] = cells[1]
    return roles


def load_ledgers(system_root: Path) -> dict[str, dict]:
    """零配置发现 CapabilityForge/*/governance/DECISION_LEDGER.json。"""
    root = Path(system_root)
    found = {}
    for child in sorted(root.iterdir()):
        if child.name.startswith(".") or not child.is_dir():
            continue
        path = child / "governance" / "DECISION_LEDGER.json"
        if path.is_file():
            found[child.name] = read_json(path)
    return found


def discover(system_root: Path, ledgers: dict[str, dict] | None = None) -> list[dict]:
    """投影系统 → 项目 → 模块 → 能力；附加历史趋势，零配置发现项目。"""
    root = Path(system_root)
    roles = project_roles(root)
    ledgers = ledgers if ledgers is not None else load_ledgers(root)
    as_of = max([d.get("last_updated", "") for d in ledgers.values()] or [""])
    as_of_dt = parse_event_ts(as_of)
    found: list[dict] = []
    for child_name, led in ledgers.items():
        child = root / child_name
        ledger_path = child / "governance" / "DECISION_LEDGER.json"
        cm = led.get("capability_model") or {}
        projects = cm.get("projects") or []
        modules = []
        for pr in projects:
            for mod in pr.get("modules") or []:
                caps = []
                for c in mod.get("caps") or []:
                    caps.append({k: c.get(k) for k in (
                        "code", "name", "domain", "level", "level_code", "completion",
                        "evidence_tier", "status", "binding_status", "next_action", "evidence"
                    ) if k in c})
                modules.append({"code": mod.get("code"), "name": mod.get("name"),
                                "completion": mod.get("completion", 0), "caps": caps})
        caps_all = [c for m in modules for c in m["caps"]]
        verified = sum(1 for c in caps_all if c.get("evidence_tier") == "verified")
        found.append({
            "dir": child.name,
            "code": projects[0].get("code") if projects else child.name.upper(),
            "title": led.get("title") or (projects[0].get("name") if projects else child.name),
            "role": roles.get(child.name, ""),
            "version": led.get("ledger_version", ""),
            "last_updated": led.get("last_updated", ""),
            "ledger": ledger_path.relative_to(root).as_posix(),
            "board": ("../" + ledger_path.parent.relative_to(root).as_posix() + "/index.html"),
            "completion": (projects[0].get("completion", 0) if projects else 0),
            "modules": modules,
            "summary": {"modules": len(modules), "capabilities": len(caps_all),
                        "verified": verified,
                        "verified_coverage": (round(verified / len(caps_all), 4) if caps_all else 0)},
            "history": history_projection(led, as_of_dt),
        })
    return found


def build_data(system_root: Path, method_root: Path = METHOD_ROOT) -> dict:
    root = Path(system_root)
    ledgers = load_ledgers(root)
    projects = discover(root, ledgers)
    return {
        "meta": {
            "schema": "system-board-data/2",
            "system": Path(system_root).resolve().name,
            "skeleton_digest": skeleton_digest(template_text(method_root)),
            "as_of": max([p.get("last_updated", "") for p in projects] or ["—"]),
            "source": ("各项目 governance/DECISION_LEDGER.json → capability_model / history；"
                       "spec_check.json → compat"),
        },
        "projects": projects,
        "compat": compat_projection(root, ledgers),
    }


def render(system_root: Path, method_root: Path = METHOD_ROOT) -> str:
    tpl = template_text(method_root)
    data = build_data(system_root, method_root)
    compact = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return DATA_RE.sub(lambda _m: "const SYSTEM_DATA = " + compact + ";\nlet DATA = SYSTEM_DATA;",
                       tpl, count=1)


def embedded_data(html: str) -> dict | None:
    m = DATA_CAPTURE_RE.search(html)
    return json.loads(m.group(1)) if m else None


def check(system_root: Path, method_root: Path = METHOD_ROOT) -> dict:
    out = Path(system_root) / OUTPUT_REL
    reasons: list[str] = []
    want_skeleton = skeleton_digest(template_text(method_root))
    if not out.is_file():
        return {"schema": SCHEMA_CHECK, "match": False, "output": OUTPUT_REL,
                "reasons": ["系统看板缺失"], "hint": "运行 build_system_board.py --apply"}
    html = out.read_text(encoding="utf-8")
    got_skeleton = skeleton_digest(html)
    if got_skeleton != want_skeleton:
        reasons.append("HTML 骨架与模板不同（手改 CSS/DOM/JS）")
    data = embedded_data(html)
    if data is None:
        reasons.append("SYSTEM_DATA 数据段缺失或被改写")
    elif data != build_data(system_root, method_root):
        reasons.append("SYSTEM_DATA 与项目账本重算结果不符（手改数据 / 账本已更新未重生成）")
    return {"schema": SCHEMA_CHECK, "match": not reasons,
            "template_digest": want_skeleton, "board_digest": got_skeleton,
            "projects": len((data or {}).get("projects") or []),
            "reasons": reasons,
            "hint": "" if not reasons else "运行 build_system_board.py --apply 重生成（禁止手改 HTML）"}


def build(system_root: Path, method_root: Path = METHOD_ROOT, *,
          apply: bool = False, approved_by: str = "") -> dict:
    if not apply:
        return {"schema": SCHEMA_BUILD, "applied": False,
                "message": "dry-run：未写盘。加 --apply 才生成"}
    if not approved_by:
        raise ValueError("生成系统看板必须提供 --approved-by（人工批准）")
    root = Path(system_root)
    out = root / OUTPUT_REL
    backup = None
    if out.is_file():
        bdir = root / BACKUP_DIR
        bdir.mkdir(parents=True, exist_ok=True)
        name = "system-board-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".html"
        shutil.copyfile(out, bdir / name)
        backup = (Path(BACKUP_DIR) / name).as_posix()
    out.parent.mkdir(parents=True, exist_ok=True)
    html = render(root, method_root)
    out.write_text(html, encoding="utf-8")
    return {"schema": SCHEMA_BUILD, "applied": True, "approved_by": approved_by,
            "output": OUTPUT_REL, "backup": backup,
            "skeleton_digest": skeleton_digest(html),
            "projects": len(build_data(root, method_root)["projects"]),
            "message": "系统看板已由模板 + 各项目账本生成；禁止手改 HTML"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--system-root", default=str(METHOD_ROOT.parent),
                    help="能力项目根（默认本脚本所在方法仓的父目录）")
    ap.add_argument("--method-root", default=str(METHOD_ROOT), help="方法论仓根（模板权威）")
    ap.add_argument("command", nargs="?", default="build", choices=("build", "check"))
    ap.add_argument("--apply", action="store_true", help="build 才写盘；默认 dry-run")
    ap.add_argument("--approved-by", default="", help="人工批准人（写盘必需）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)
    try:
        if args.command == "check":
            result = check(Path(args.system_root), Path(args.method_root))
            rc = 0 if result["match"] else 1
        else:
            result = build(Path(args.system_root), Path(args.method_root),
                           apply=args.apply, approved_by=args.approved_by)
            rc = 0
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    if args.json or args.command == "check":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False))
    return rc


if __name__ == "__main__":
    sys.exit(main())
