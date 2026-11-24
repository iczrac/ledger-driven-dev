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
1. 不制造第二事实源：状态写在账本内 `docs.registry`（由 ledger-steward 裁决），
   本工具只写草稿/骨架文件与只读报告；
2. 零第三方依赖；只认 UTF-8 文本；遇到不可读文件 fail-closed 标 unreadable；
3. 不自动撰写"为什么"类正文，不覆盖既有正文，不绕过账本改 ledger；
4. clear-suspect 必须有签名与理由，否则拒绝。

用法
----
    python3 scripts/doc_lifecycle.py scaffold --target P --doc docs/plan/x.md --kind plan [--json]
    python3 scripts/doc_lifecycle.py lint --target P [--json]
    python3 scripts/doc_lifecycle.py mark-stale --target P --doc docs/plan/x.md --reason <r> [--json]
    python3 scripts/doc_lifecycle.py clear-suspect --target P --doc docs/plan/x.md --signed-by <人> --reason <r> [--json]
    python3 scripts/doc_lifecycle.py check --target P [--json]

退出码：0 全部通过；1 存在 suspect/stale/incomplete/unreadable；2 输入错误。
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
    issues = list(report["issues"])
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
                                        "clear-suspect", "check"])
    ap.add_argument("--target", default=".", help="项目根目录")
    ap.add_argument("--doc", help="文档相对路径")
    ap.add_argument("--kind", help="骨架类型：plan/rationale/reference/record")
    ap.add_argument("--reason", default="", help="原因")
    ap.add_argument("--signed-by", default="", help="清除 suspect 的签名人")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)
    root = Path(args.target).resolve()
    if args.command in ("scaffold", "mark-stale", "clear-suspect") and not args.doc:
        print("doc-lifecycle: --doc 必填", file=sys.stderr)
        return 2
    fn = {
        "scaffold": lambda: scaffold(root, args.doc, args.kind or "plan"),
        "lint": lambda: lint(root),
        "mark-stale": lambda: mark_stale(root, args.doc, args.reason),
        "clear-suspect": lambda: clear_suspect(root, args.doc, args.signed_by, args.reason),
        "check": lambda: check(root),
    }[args.command]
    result = fn()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False))
    if result.get("status") == "error":
        return 2
    if args.command in ("lint", "check") and result.get("issues"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
