#!/usr/bin/env python3
"""从规范化文档抽取目标架构（文档 → 规划图）。

与 discover_project.py（文件系统 → 现状草稿）互补：本脚本读的是人写下的目标——
PROJECT_BRIEF 的目标、MODULE_MAP 的模块、CAPABILITY_INDEX 的编码与依赖，产出
TARGET_ARCHITECTURE.json，供 compare_graphs.py 与实际能力图比对。

用法：
    python3 scripts/architect_from_docs.py --target /path/to/project --dry-run
    python3 scripts/architect_from_docs.py --target /path/to/project
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from trace_common import load_json, rel_path, write_if_absent

CODE_RE = re.compile(r"\b([A-Z][A-Z0-9]*)\.([A-Z][A-Z0-9]*)\.([A-Z][A-Z0-9]*)\.(\d{2})\b")
DEP_RE = re.compile(r"依赖\s*[:：]\s*((?:[A-Z][A-Z0-9]*\.){3}\d{2}(?:\s*[,，、]\s*(?:[A-Z][A-Z0-9]*\.){3}\d{2})*)")
TARGET_RE = re.compile(r"目标\s*[:：]\s*L([0-5])")


def _section(text: str, title: str) -> list[str]:
    lines = text.splitlines()
    out: list[str] = []
    inside = False
    for line in lines:
        if line.startswith("## "):
            inside = line.strip() == f"## {title}"
            continue
        if inside and line.strip().startswith("- "):
            out.append(line.strip()[2:].strip())
    return out


def build(target: Path, docs_dir: Path, registry: dict) -> dict:
    files = sorted(p for p in docs_dir.rglob("*.md") if p.is_file()) if docs_dir.exists() else []
    texts = {rel_path(p, target): p.read_text(encoding="utf-8", errors="replace") for p in files}
    warnings: list[str] = []
    if not texts:
        warnings.append("未发现文档；目标架构为空，请先运行 rebuild_docs.py 或手工写规划文档。")

    codes: dict[str, dict] = {}
    for src, text in texts.items():
        for m in CODE_RE.finditer(text):
            code = m.group(0)
            entry = codes.setdefault(code, {"code": code, "sources": [], "name": "",
                                            "depends_on": [], "target_level": None})
            if src not in entry["sources"]:
                entry["sources"].append(src)
            for line in text.splitlines():
                if code in line and (tl := TARGET_RE.search(line)):
                    entry["target_level"] = f"L{tl.group(1)}"
            # 表格行中的第二列常是能力名
            row = next((l for l in text.splitlines() if l.startswith("| " + code + " |")), "")
            if row:
                cells = [c.strip() for c in row.strip("|").split("|")]
                if len(cells) > 2 and cells[2] and not entry["name"]:
                    entry["name"] = cells[2]
        for dep in DEP_RE.finditer(text):
            parent = None
            for m in CODE_RE.finditer(text[:dep.start()]):
                parent = m.group(0)
            if parent and parent in codes:
                found = CODE_RE.findall(dep.group(1))
                for a, b, c, n in found:
                    child = f"{a}.{b}.{c}.{n}"
                    if child != parent and child not in codes[parent]["depends_on"]:
                        codes[parent]["depends_on"].append(child)

    brief = next((v for k, v in texts.items() if k.endswith("PROJECT_BRIEF.md")), "")
    goals = _section(brief, "目标")
    if not goals:
        warnings.append("PROJECT_BRIEF.md 缺少「## 目标」小节；目标架构将只包含编码结构。")
        goals = [f"覆盖能力 {len(codes)} 项（由文档编码推断）"] if codes else []

    modules: dict[str, dict] = {}
    map_text = next((v for k, v in texts.items() if k.endswith("MODULE_MAP.md")), "")
    for line in map_text.splitlines():
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4 or not re.fullmatch(r"[A-Z][A-Z0-9]*", cells[0]) or cells[0] == "模块":
            continue
        mcode, name, src, cap_cells = cells[0], cells[1], cells[2], cells[3]
        modules[mcode] = {
            "code": mcode, "name": name,
            "src": [x.strip("` ") for x in src.split(",") if x.strip() and x.strip() != "（无）"],
            "caps": [c["code"] for c in codes.values()
                     if c["code"].split(".")[1] == mcode] if cap_cells == "" else
                    CODE_RE.findall(cap_cells.replace("(", "").replace(")", "")),
        }
        modules[mcode]["caps"] = [f"{a}.{b}.{c}.{n}" for a, b, c, n in modules[mcode]["caps"]]

    if not modules and codes:
        for code, info in codes.items():
            mcode = code.split(".")[1]
            modules.setdefault(mcode, {"code": mcode, "name": mcode, "src": [], "caps": []})
            modules[mcode]["caps"].append(code)
        warnings.append("未解析到 MODULE_MAP 表格；模块名与 src 由编码推断，请人工校准。")

    project_code = str(registry.get("project", {}).get("code", "")).upper()
    if not project_code and codes:
        project_code = next(iter(codes.values()))["code"].split(".")[0]
    confidence = "high" if goals and modules and codes else ("medium" if codes else "low")
    return {
        "schema": "target-arch/1",
        "source": "documentation",
        "project": {
            "code": project_code,
            "name": str(registry.get("project", {}).get("name", project_code)),
        },
        "goals": goals,
        "modules": [modules[k] for k in sorted(modules)],
        "capabilities": [codes[k] for k in sorted(codes)],
        "source_docs": sorted(texts),
        "warnings": warnings,
        "confidence": confidence,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default=".", help="项目根目录")
    ap.add_argument("--docs-dir", help="文档目录（默认 <target>/docs）")
    ap.add_argument("--out", help="输出路径（默认 <target>/governance/TARGET_ARCHITECTURE.json）")
    ap.add_argument("--force", action="store_true", help="覆盖既有目标架构")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    target = Path(args.target).expanduser().resolve()
    docs = Path(args.docs_dir).expanduser().resolve() if args.docs_dir else target / "docs"
    gov = target / "governance"
    reg_path = gov / "registry.json"
    registry = load_json(reg_path, "registry") if reg_path.exists() else {}
    result = build(target, docs, registry)
    out = Path(args.out).expanduser().resolve() if args.out else gov / "TARGET_ARCHITECTURE.json"

    if not args.dry_run:
        status = write_if_absent(out, json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                 args.force)
        if not args.json:
            print(f"[{status}] {out}")
    if args.json or args.dry_run:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"目标架构：模块 {len(result['modules'])} / 能力 {len(result['capabilities'])} "
              f"/ 目标 {len(result['goals'])}，置信度 {result['confidence']}")
        for w in result["warnings"]:
            print(f"[WARN] {w}")
        if not sys.stdout.isatty():
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
