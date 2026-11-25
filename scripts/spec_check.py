#!/usr/bin/env python3
"""规范型仓库通用自查器：术语残留 / 版本一致 / 派生漂移 / 必备文件 / 链接解析。

第一性原理
----------
规范型仓库（主体是 Markdown 规范、无代码符号可绑定的包）的错误从不先出现在
运行时：它们先出现在文本里——改名漏了一处 CJK 相邻的旧名、三处版本号只同步了
两处、生成物被手改而无人知、README 链接指向已删除的文件。这些错误可判定，就
必须交给判据而不是靠人工走查的运气。本工具把五类判据做成通用、配置驱动：

  - forbidden_terms  术语残留：禁止词必须为零（ASCII 词自动按独立词匹配，
                     规避 `\\b` 把汉字当词符的假阴性教训——改用 ASCII 环视）；
  - version          版本一致：全部声明位置必须等于唯一权威版本；
  - generated        派生漂移：重建命令跑完后与快照逐字节比对，跑完即还原，
                     检查等效只读；
  - required         必备文件：声明存在的文件必须存在；
  - links            链接解析：列出文档中的相对链接必须能落到真实文件。

口径
----
缺配置节 = `applicable=false`（`n/a`），不冒充 `0`；`0` 与 `n/a` 分开计数——
沿用 v2.25.0 的门禁真相原则。不可读文件 fail-closed 记为命中。

纪律
----
1. 零第三方依赖；只认 UTF-8 文本；
2. 只读仓库内容（generated 检查跑完重建命令后按快照还原）；
3. 配置文件 `spec_check.json` 是唯一输入，不内嵌任何仓库专属词表；
4. 不自动修复：只报告，修复由人或宿主工作流决定。

用法
----
    python3 scripts/spec_check.py --target <repo> [--json] [--no-rebuild]

退出码：0 无命中；1 存在命中；2 输入错误（缺配置 / 配置非法）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

SCHEMA = "spec-check/1"
ASCII_WORD_RE_TMPL = r"(?<![A-Za-z]){0}(?![A-Za-z])"
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _load_config(target: Path) -> dict:
    cfg_path = target / "spec_check.json"
    if not cfg_path.is_file():
        raise FileNotFoundError(f"配置不存在：{cfg_path}")
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"配置不可读或非法：{exc}") from exc
    if cfg.get("schema") != SCHEMA:
        raise ValueError(f"配置 schema 必须为 {SCHEMA}，实际 {cfg.get('schema')!r}")
    return cfg


def _iter_files(target: Path, scan: dict) -> list[Path]:
    include = scan.get("include", ["**/*.md", "**/*.py", "**/*.json"])
    exclude = [e.rstrip("/") for e in scan.get("exclude", [])]
    exclude.append("spec_check.json")  # 配置自身含禁词，必须排除
    found: set[Path] = set()
    for pattern in include:
        for p in target.glob(pattern):
            if p.is_file():
                found.add(p)
    out = []
    for p in sorted(found):
        rel = p.relative_to(target).as_posix()
        if any(rel == ex or rel.startswith(ex + "/") or p.match(ex) for ex in exclude):
            continue
        out.append(p)
    return out


def check_terms(target: Path, cfg: dict) -> dict:
    terms = cfg.get("forbidden_terms")
    if not terms:
        return {"metric": "forbidden_terms", "applicable": False, "hits": 0}
    scan = cfg.get("scan", {})
    hits: list[dict] = []
    unreadable = 0
    patterns = []
    for term in terms:
        if re.fullmatch(r"[A-Za-z0-9_-]+", term):
            patterns.append((term, re.compile(ASCII_WORD_RE_TMPL.format(re.escape(term)))))
        else:
            patterns.append((term, None))
    for p in _iter_files(target, scan):
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            unreadable += 1
            hits.append({"file": p.relative_to(target).as_posix(), "reason": "unreadable"})
            continue
        for term, pat in patterns:
            n = len(pat.findall(text)) if pat else text.count(term)
            if n:
                hits.append({"file": p.relative_to(target).as_posix(), "term": term, "count": n})
    return {"metric": "forbidden_terms", "applicable": True, "hits": len(hits),
            "unreadable": unreadable, "detail": hits}


def check_version(target: Path, cfg: dict) -> dict:
    spec = cfg.get("version")
    if not spec:
        return {"metric": "version", "applicable": False, "hits": 0}
    canonical = spec.get("canonical")
    if not canonical:
        src = spec.get("canonical_from", {})
        data = json.loads((target / src["file"]).read_text(encoding="utf-8"))
        for key in src["json_key"].split("."):
            data = data[key]
        canonical = str(data)
    hits: list[dict] = []
    declared = 0
    for d in spec.get("declarations", []):
        path = target / d["file"]
        try:
            if "json_key" in d:
                data = json.loads(path.read_text(encoding="utf-8"))
                for key in d["json_key"].split("."):
                    data = data[key]
                value = str(data)
            else:
                m = re.search(d["regex"], path.read_text(encoding="utf-8"))
                value = m.group(1) if m else None
        except (OSError, KeyError, ValueError, re.error, IndexError):
            hits.append({"file": d["file"], "reason": "unreadable_or_invalid"})
            continue
        if value is None:
            hits.append({"file": d["file"], "reason": "declaration_not_found"})
            continue
        declared += 1
        if value != canonical:
            hits.append({"file": d["file"], "found": value, "expected": canonical})
    return {"metric": "version", "applicable": True, "hits": len(hits),
            "canonical": canonical, "declarations_checked": declared, "detail": hits}


def check_generated(target: Path, cfg: dict, run_rebuild: bool = True) -> dict:
    spec = cfg.get("generated")
    if not spec:
        return {"metric": "generated_drift", "applicable": False, "hits": 0}
    paths = [target / p for p in spec.get("paths", [])]

    def snapshot() -> dict[str, bytes]:
        out: dict[str, bytes] = {}
        for base in paths:
            if not base.exists():
                continue
            for p in sorted(base.rglob("*")):
                if p.is_file():
                    out[p.relative_to(target).as_posix()] = p.read_bytes()
        return out

    before = snapshot()
    if not run_rebuild:
        return {"metric": "generated_drift", "applicable": True, "hits": 0,
                "note": "skipped (--no-rebuild)", "files": len(before)}
    cmd = spec.get("rebuild_cmd")
    if not cmd:
        return {"metric": "generated_drift", "applicable": True, "hits": 0,
                "note": "no rebuild_cmd configured", "files": len(before)}
    proc = subprocess.run(cmd, cwd=target, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        return {"metric": "generated_drift", "applicable": True, "hits": 1,
                "detail": [{"reason": "rebuild_failed", "stderr": proc.stderr[-400:]}]}
    after = snapshot()
    drifted = sorted(k for k in set(before) | set(after)
                     if before.get(k) != after.get(k))
    # 还原：按快照写回原始内容并删除重建新增的文件，使检查等效只读。
    restored, removed = 0, 0
    for rel, content in before.items():
        p = target / rel
        if after.get(rel) != content:
            try:
                p.write_bytes(content)
                restored += 1
            except OSError:
                pass
    for rel in set(after) - set(before):
        try:
            (target / rel).unlink()
            removed += 1
        except OSError:
            pass
    return {"metric": "generated_drift", "applicable": True, "hits": len(drifted),
            "detail": [{"file": k, "state": "changed" if k in before else "created"}
                       for k in drifted],
            "files_before": len(before), "files_after": len(after),
            "restored": restored, "removed": removed}


def check_required(target: Path, cfg: dict) -> dict:
    req = cfg.get("required")
    if not req:
        return {"metric": "required_files", "applicable": False, "hits": 0}
    hits = [{"file": f, "reason": "missing"} for f in req if not (target / f).is_file()]
    return {"metric": "required_files", "applicable": True, "hits": len(hits), "detail": hits}


def check_links(target: Path, cfg: dict) -> dict:
    docs = cfg.get("links", {}).get("docs")
    if not docs:
        return {"metric": "broken_links", "applicable": False, "hits": 0}
    hits: list[dict] = []
    checked = 0
    for rel in docs:
        p = target / rel
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            hits.append({"file": rel, "reason": "unreadable"})
            continue
        for m in LINK_RE.finditer(text):
            link = m.group(1)
            if link.startswith(("http://", "https://", "mailto:", "#")):
                continue
            checked += 1
            dest = link.split("#")[0].split("?")[0].strip()
            if not dest:
                continue
            if not (p.parent / dest).exists():
                hits.append({"file": rel, "link": link})
    return {"metric": "broken_links", "applicable": True, "hits": len(hits),
            "links_checked": checked, "detail": hits}


def run_check(target: Path, run_rebuild: bool = True) -> dict:
    cfg = _load_config(target)
    results = [
        check_terms(target, cfg),
        check_version(target, cfg),
        check_generated(target, cfg, run_rebuild),
        check_required(target, cfg),
        check_links(target, cfg),
    ]
    applicable = sum(1 for r in results if r["applicable"])
    hits = sum(r["hits"] for r in results if r["applicable"])
    return {"schema": SCHEMA, "target": target.name, "ok": hits == 0,
            "metrics": results, "applicable": applicable, "na": len(results) - applicable,
            "total_hits": hits}


def main() -> int:
    ap = argparse.ArgumentParser(description="规范型仓库通用自查器（spec-check/1）")
    ap.add_argument("--target", default=".", help="仓库根目录（含 spec_check.json）")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--no-rebuild", action="store_true", help="跳过派生重建检查")
    args = ap.parse_args()
    target = Path(args.target).resolve()
    try:
        report = run_check(target, run_rebuild=not args.no_rebuild)
    except (FileNotFoundError, ValueError) as exc:
        print(f"输入错误：{exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"spec-check · 目标 {report['target']} · 适用 {report['applicable']} 项 / n-a {report['na']} 项")
        for r in report["metrics"]:
            state = "n/a" if not r["applicable"] else str(r["hits"])
            print(f"  {r['metric']:<18} 命中 {state}")
        print("通过" if report["ok"] else "存在命中")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
