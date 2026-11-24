#!/usr/bin/env python3
"""文档生命周期工具：scaffold / lint / mark-stale / clear-suspect / check。

第一性原理
----------
文档的"信任"不能靠人写"已核验"三个字：它必须能从上游指纹、生成时间与
状态词复算。本工具只读账本与文档，产出三类可复算结论：
  - incomplete：骨架未人工填写（含 `<!-- 待人工填写 -->`）；
  - suspect：上游 source_hash 变化后未 clear；
  - stale：stale_after 已过期或未复核的 plan 文档。
骨架永不判 compliant：AI 生成结构不等于人工确认语义。

纪律
----
1. 不制造第二事实源：状态写在账本内 `docs.registry`（由 ledger-steward 裁决）；
   `seed` / `approve` 是唯一经人批准写该账本字段的入口，其余命令只读；
2. 零第三方依赖；只认 UTF-8 文本；遇到不可读文件 fail-closed 标 unreadable；
3. 不自动撰写"为什么"类正文，不覆盖既有正文；`seed` 初判一律 draft/verified 为空，
   绝不批量标 current；
4. clear-suspect 与 `approve --status current` 必须有人工签名与理由，且后者还要
   有可复算 source_hash，否则拒绝。

用法
----
    python3 scripts/doc_lifecycle.py scaffold --target P --doc docs/plans/x_PLAN.md --kind plan [--json]
    python3 scripts/doc_lifecycle.py lint --target P [--json]
    python3 scripts/doc_lifecycle.py mark-stale --target P --doc docs/plans/x_PLAN.md --reason <r> [--json]
    python3 scripts/doc_lifecycle.py clear-suspect --target P --doc docs/plans/x_PLAN.md --signed-by <人> --reason <r> [--json]
    python3 scripts/doc_lifecycle.py check --target P [--json]
    python3 scripts/doc_lifecycle.py gate --target P [--strict] [--json]
    python3 scripts/doc_lifecycle.py seed --target P --approved-by ledger-steward [--json]
    python3 scripts/doc_lifecycle.py approve --target P --doc D --status current --signed-by <人> --reason <r> [--json]

退出码：0 全部通过；1 存在 suspect/stale/incomplete/unreadable；2 输入错误。
`gate` 默认只告警（exit 0），`--strict` 才阻断；`seed` / `approve` 写入账本并进历史链。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "doc-lifecycle/1"
PLACEHOLDER = "<!-- 待人工填写 -->"
VALID_KINDS = {"plan", "rationale", "reference", "record"}
VALID_STATUS = {"draft", "incomplete", "suspect", "stale", "verified", "unbound"}
# 状态词来自既有 ontology 词表（此处为白名单，不新增第二词表）
STATUS_WORDS = ("draft", "incomplete", "suspect", "stale", "verified", "unbound")
# 规划语义：仓库没有单独的 PLAN_RE 常量，这里以既有路径/标题口径作确定性初判。
PLAN_HINTS = ("/plans/", "_PLAN.md", "计划：")
CODE_RE = re.compile(r"\b[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9]*\.\d{2}\b")
DECISION_RE = re.compile(r"\bD-\d+\b")

TEMPLATES = {
    "plan": "# 计划：<标题>\n\n" + PLACEHOLDER + "\n\n## 目标\n\n" + PLACEHOLDER +
            "\n\n## 义务\n\n- owner: " + PLACEHOLDER + "\n- stale_after: " + PLACEHOLDER + "\n",
    "rationale": "# 设计理由：<标题>\n\n" + PLACEHOLDER +
                 "\n\n## 为什么\n\n" + PLACEHOLDER + "\n",
    "reference": "# 参考：<标题>\n\n" + PLACEHOLDER + "\n",
    "record": "# 记录：<标题>\n\n" + PLACEHOLDER + "\n",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _registry_path(root: Path) -> Path:
    return root / "governance" / "DECISION_LEDGER.json"


def _load_registry(root: Path) -> dict:
    p = _registry_path(root)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data.get("docs", {}).get("registry", {})


def _load_ledger(root: Path) -> dict:
    data = json.loads(_registry_path(root).read_text(encoding="utf-8"))
    return data


def _history_append(ledger: dict, kind: str, detail: dict) -> None:
    """只追加事件，不改能力模型状态：沿用末事件 state_digest 与指纹。"""
    hist = ledger.setdefault("history", {})
    events = hist.setdefault("events", [])
    last = events[-1] if events else {}
    fp = last.get("fingerprint_after") or "0000000000000000"
    events.append({
        "seq": int(last.get("seq", 0)) + 1,
        "ts": str(ledger.get("last_updated") or last.get("ts") or "1970-01-01T00:00:00Z"),
        "type": kind,
        "fingerprint_before": fp,
        "fingerprint_after": fp,
        "changes": detail,
        "state_digest": json.loads(json.dumps(last.get("state_digest") or {})),
        "trigger": detail.get("approved_by", "doc-lifecycle"),
        "note": "文档生命周期写入：能力模型未变，指纹与末事件保持一致",
    })


def _save_ledger(root: Path, ledger: dict) -> None:
    _registry_path(root).write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _classify(path: str, text: str) -> str:
    if path.startswith("docs/generated/"):
        return "derived"
    if any(h in path or h in text[:400] for h in PLAN_HINTS):
        return "plan"
    if path.endswith("STANDARD.md") or re.match(r"docs/\d\d-", path):
        return "rationale"
    return "reference"


def seed(root: Path, approved_by: str) -> dict:
    """确定性初判并写入账本 docs.registry；不写 current、不新建第二登记表。"""
    if not approved_by.strip():
        return {"schema": SCHEMA, "command": "seed", "status": "error",
                "reason": "seed 必须给出批准人（--approved-by），禁止匿名播种"}
    docs = _scan(root)
    ledger = _load_ledger(root)
    existing = (ledger.get("docs", {}) or {}).get("registry", {}) or {}
    wanted: dict[str, dict] = {}
    for doc in docs:
        path = doc["path"]
        text = (root / path).read_text(encoding="utf-8")
        wanted[path] = {
            "kind": _classify(path, text),
            "status": "draft",
            "source_hash": doc.get("source_hash", ""),
            "generated_from": None,
            "verified": [],
            "covers": {"codes": sorted(set(CODE_RE.findall(text))),
                       "decisions": sorted(set(DECISION_RE.findall(text)))},
            "owner": None,
            "stale_after": None,
            "approved_by": approved_by,
        }
    if existing == wanted:
        return {"schema": SCHEMA, "command": "seed", "status": "noop", "draft": len(wanted),
                "reason": "登记已一致，未写账本、未追加事件"}
    added = sorted(set(wanted) - set(existing))
    removed = sorted(set(existing) - set(wanted))
    modified = sorted(p for p in set(wanted) & set(existing) if wanted[p] != existing[p])
    ledger.setdefault("docs", {})["registry"] = wanted
    _history_append(ledger, "doc_registry_seed", {
        "approved_by": approved_by, "role": "ledger-steward",
        "added": added, "removed": removed, "modified": modified,
        "initial_status": "draft", "current_count": 0,
    })
    _save_ledger(root, ledger)
    return {"schema": SCHEMA, "command": "seed", "status": "seeded",
            "draft": len(wanted), "added": len(added), "removed": len(removed),
            "modified": len(modified),
            "approved_by": approved_by, "registry": "governance/DECISION_LEDGER.json#docs.registry"}


def approve(root: Path, doc: str, status: str, signed_by: str,
            reason: str, source_hash: str = "") -> dict:
    """把登记状态改为 current 必须同时有人工签名与可复算 source_hash。"""
    if status != "current":
        return {"schema": SCHEMA, "command": "approve", "status": "error",
                "reason": "仅允许人工把 draft/suspect 升为 current；不得直接写 verified"}
    if not signed_by.strip() or not reason.strip():
        return {"schema": SCHEMA, "command": "approve", "status": "error",
                "reason": "升 current 必须同时给出签名与理由，无签名一律拒绝"}
    ledger = _load_ledger(root)
    reg = (ledger.get("docs", {}) or {}).get("registry", {}) or {}
    meta = reg.get(doc)
    if not isinstance(meta, dict):
        return {"schema": SCHEMA, "command": "approve", "status": "error",
                "reason": "文档未登记于 docs.registry，请先 seed"}
    p = root / doc
    if not p.exists():
        return {"schema": SCHEMA, "command": "approve", "status": "error",
                "reason": "文档不存在"}
    actual = _sha(p.read_text(encoding="utf-8"))
    if source_hash and source_hash != actual:
        return {"schema": SCHEMA, "command": "approve", "status": "error",
                "reason": "source_hash 与当前正文不一致，禁止凭空批准"}
    meta["status"] = "current"
    meta["source_hash"] = actual
    meta["generated_from"] = meta.get("generated_from") or "人工复核正文（签名背书）"
    meta["verified"] = {"signed_by": signed_by, "reason": reason, "at": _now(),
                        "source_hash": actual}
    _history_append(ledger, "doc_registry_approve", {
        "approved_by": signed_by, "role": "ledger-steward",
        "doc": doc, "status": "current", "reason": reason,
    })
    _save_ledger(root, ledger)
    return {"schema": SCHEMA, "command": "approve", "status": "current",
            "path": doc, "signed_by": signed_by, "source_hash": actual}


def gate(root: Path, strict: bool = False) -> dict:
    """统一门禁节：默认 warn 不阻断；--strict 才让退出码非 0。"""
    report = check(root)
    issues = report["issues"]
    counts: dict[str, int] = {}
    for item in issues:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    counts["trust"] = sum(1 for c in report["checks"]
                          if c["id"] in ("doc_trust", "doc_coverage", "doc_obligation")
                          and c["status"] == "warn")
    has_problem = bool(issues) or counts["trust"] > 0
    return {"schema": SCHEMA, "command": "gate", "mode": "strict" if strict else "shadow",
            "status": "fail" if (strict and has_problem) else ("warn" if has_problem else "ok"),
            "counts": counts,
            "issues": [{"path": i.get("path", ""), "status": i["status"],
                        "reason": i.get("reason", "")} for i in issues],
            "trust_warnings": [c for c in report["checks"]
                               if c["status"] == "warn" and c["id"] in
                               ("doc_trust", "doc_coverage", "doc_obligation")]}


def _scan(root: Path) -> list[dict]:
    docs = []
    for p in sorted((root / "docs").rglob("*.md")) if (root / "docs").exists() else []:
        rel = p.relative_to(root).as_posix()
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            docs.append({"path": rel, "status": "unreadable", "reason": "文件不可读"})
            continue
        status = "draft"
        if PLACEHOLDER in text:
            status = "incomplete"
        found = [w for w in STATUS_WORDS if re.search(rf"(?m)^\s*status:\s*{w}\b", text)]
        if found:
            status = found[-1]
        docs.append({"path": rel, "status": status,
                     "source_hash": _sha(text), "generated_at": _now()})
    return docs


def scaffold(root: Path, doc: str, kind: str) -> dict:
    if kind not in VALID_KINDS:
        return {"schema": SCHEMA, "command": "scaffold", "status": "error",
                "reason": f"非法 kind {kind!r}，合法：{sorted(VALID_KINDS)}"}
    target = (root / doc).resolve()
    if not str(target).startswith(str(root.resolve())):
        return {"schema": SCHEMA, "command": "scaffold", "status": "error",
                "reason": "文档路径越出目标目录"}
    if target.exists():
        return {"schema": SCHEMA, "command": "scaffold", "status": "error",
                "reason": "骨架已存在，禁止覆盖既有正文"}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(TEMPLATES[kind], encoding="utf-8")
    return {"schema": SCHEMA, "command": "scaffold", "status": "incomplete",
            "path": doc, "kind": kind,
            "reason": "骨架含待人工填写标记，不得判 compliant"}


def lint(root: Path) -> dict:
    docs = _scan(root)
    reg = _load_registry(root)
    issues = []
    for d in docs:
        if d["status"] in ("incomplete", "unreadable", "suspect", "stale"):
            issues.append({"path": d["path"], "status": d["status"],
                           "reason": d.get("reason", f"状态词={d['status']}")})
        if d["path"] not in reg and d["status"] != "incomplete":
            issues.append({"path": d["path"], "status": "orphan",
                           "reason": "未登记于 docs.registry"})
    ok = not issues
    return {"schema": SCHEMA, "command": "lint", "docs": docs, "issues": issues,
            "status": "ok" if ok else "incomplete",
            "summary": {"total": len(docs), "issues": len(issues)}}


def mark_stale(root: Path, doc: str, reason: str) -> dict:
    if not reason.strip():
        return {"schema": SCHEMA, "command": "mark-stale", "status": "error",
                "reason": "mark-stale 必须给出原因"}
    p = root / doc
    if not p.exists():
        return {"schema": SCHEMA, "command": "mark-stale", "status": "error",
                "reason": "文档不存在"}
    return {"schema": SCHEMA, "command": "mark-stale", "status": "suspect",
            "path": doc, "reason": reason, "at": _now(),
            "hint": "状态裁决须由 ledger-steward 写入 docs.registry；本工具不写账本"}


def clear_suspect(root: Path, doc: str, signed_by: str, reason: str) -> dict:
    if not signed_by.strip() or not reason.strip():
        return {"schema": SCHEMA, "command": "clear-suspect", "status": "error",
                "reason": "clear-suspect 必须同时给出签名与理由"}
    p = root / doc
    if not p.exists():
        return {"schema": SCHEMA, "command": "clear-suspect", "status": "error",
                "reason": "文档不存在"}
    return {"schema": SCHEMA, "command": "clear-suspect", "status": "cleared",
            "path": doc, "signed_by": signed_by, "reason": reason, "at": _now(),
            "hint": "清除结果须由 ledger-steward 写回 docs.registry；本工具不写账本"}


def _stale_after_expired(value: object) -> bool:
    """stale_after 早于今天即过期；占位符/非法值不猜（fail-closed 为未过期）。"""
    if not isinstance(value, str) or not value.strip() or PLACEHOLDER in value:
        return False
    try:
        day = datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return False
    return day < datetime.now(timezone.utc).date()


def check(root: Path) -> dict:
    """文档不变量的只读投影；新判据先 shadow：只告警不改状态。"""
    report = lint(root)
    docs = report["docs"]
    reg = _load_registry(root)
    issues = list(report["issues"])
    # 登记后正文被手改：source_hash 不再复算得出，标 suspect（不改账本状态）。
    for path, meta in reg.items():
        if not isinstance(meta, dict) or not meta.get("source_hash"):
            continue
        live = next((d for d in docs if d["path"] == path), None)
        if live and live.get("source_hash") != meta["source_hash"]:
            issues.append({"path": path, "status": "suspect",
                           "reason": "正文与登记 source_hash 不一致，需人工复核"})
    checks = []
    # 1 覆盖完整：registry 声明的文档必须存在
    missing = [p for p in reg if not (root / p).exists()]
    checks.append({"id": "doc_coverage", "status": "pass" if not missing else "warn",
                   "detail": "覆盖完整" if not missing else f"缺失：{missing}"})
    # 2 派生可复算：骨架/状态词可从文件复算（_scan 已复算）
    recomputable = all("status" in d and "source_hash" in d for d in docs)
    checks.append({"id": "doc_derived", "status": "pass" if recomputable else "warn",
                   "detail": "派生可复算"})
    # 3 信任一致：verified 必须同时具备 source_hash 与 generated_at
    bad_trust = [d["path"] for d in docs if d["status"] == "verified"
                 and not (d.get("source_hash") and d.get("generated_at"))]
    for path, meta in reg.items():
        v = meta.get("verified") if isinstance(meta, dict) else None
        if v and not (meta.get("source_hash") and meta.get("generated_from")):
            bad_trust.append(path)
    checks.append({"id": "doc_trust", "status": "pass" if not bad_trust else "warn",
                   "detail": "信任一致" if not bad_trust else f"异常：{bad_trust}"})
    # 4 义务已声明：非骨架文档应在 registry 中有义务声明
    undeclared = [d["path"] for d in docs
                  if d["status"] not in ("incomplete", "draft") and d["path"] not in reg]
    checks.append({"id": "doc_obligation", "status": "pass" if not undeclared else "warn",
                   "detail": "义务已声明" if not undeclared else f"未声明：{undeclared}"})
    # 5 无孤儿：孤儿文档即未登记的文档
    orphans = [i["path"] for i in report["issues"] if i["status"] == "orphan"]
    checks.append({"id": "doc_no_orphan", "status": "pass" if not orphans else "warn",
                   "detail": "无孤儿" if not orphans else f"孤儿：{orphans}"})
    # stale：stale_after 过期或未复核的 plan 文档（只告警，不改账本状态）
    for path, meta in reg.items():
        if not isinstance(meta, dict):
            continue
        expired = _stale_after_expired(meta.get("stale_after"))
        verified = str(meta.get("status", "")) in ("verified", "compliant")
        if expired and not verified:
            issues.append({"path": path, "status": "stale",
                           "reason": f"stale_after={meta['stale_after']} 已过期且未复核"})
    ok = all(c["status"] == "pass" for c in checks) and not issues
    return {"schema": SCHEMA, "command": "check", "mode": "shadow",
            "status": "ok" if ok else "warn", "checks": checks,
            "docs": docs, "issues": issues,
            "note": "新判据先 shadow：只告警不改状态；升硬门须人批准"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["scaffold", "lint", "mark-stale",
                                        "clear-suspect", "check", "gate", "seed", "approve"])
    ap.add_argument("--target", default=".", help="项目根目录")
    ap.add_argument("--doc", help="文档相对路径")
    ap.add_argument("--kind", help="骨架类型：plan/rationale/reference/record")
    ap.add_argument("--reason", default="", help="原因")
    ap.add_argument("--signed-by", default="", help="清除 suspect / 批准 current 的签名人")
    ap.add_argument("--approved-by", default="", help="ledger-steward 批准人")
    ap.add_argument("--status", default="", help="approve 的目标状态（仅 current）")
    ap.add_argument("--source-hash", default="", help="批准 current 时可复算的正文摘要")
    ap.add_argument("--strict", action="store_true", help="gate 遇告警时阻断（默认只告警）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)
    root = Path(args.target).resolve()
    if args.command in ("scaffold", "mark-stale", "clear-suspect", "approve") and not args.doc:
        print("doc-lifecycle: --doc 必填", file=sys.stderr)
        return 2
    fn = {
        "scaffold": lambda: scaffold(root, args.doc, args.kind or "plan"),
        "lint": lambda: lint(root),
        "mark-stale": lambda: mark_stale(root, args.doc, args.reason),
        "clear-suspect": lambda: clear_suspect(root, args.doc, args.signed_by, args.reason),
        "check": lambda: check(root),
        "gate": lambda: gate(root, args.strict),
        "seed": lambda: seed(root, args.approved_by),
        "approve": lambda: approve(root, args.doc, args.status, args.signed_by,
                                   args.reason, args.source_hash),
    }[args.command]
    result = fn()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False))
    if result.get("status") == "error":
        return 2
    if args.command == "gate":
        return 1 if result.get("status") == "fail" else 0
    if args.command in ("lint", "check") and result.get("issues"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
